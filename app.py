import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# === Load Data ===
@st.cache_data
def load_data():
    summary = pd.read_excel("Daily_Summary_with_Prioritized_Signal.xlsx")
    summary.columns = summary.columns.str.strip()
    df_30 = pd.read_csv("NSE_NIFTY, 30.csv", parse_dates=["time"])
    df_5 = pd.read_csv("NIFTY_5min_All_Sorted.csv", parse_dates=["time"])

    # Extract dates for easier comparison
    df_30["date"] = df_30["time"].dt.date
    df_5["date"] = df_5["time"].dt.date
    summary["Date"] = pd.to_datetime(summary["Date"], dayfirst=True)
    summary["date"] = summary["Date"].dt.date

    return summary, df_30, df_5

# Load and prepare data
summary, df_30min, df_5min = load_data()
available_5min_dates = set(df_5min["date"].unique())
available_30min_dates = set(df_30min["date"].unique())

# === App Title ===
st.title("NIFTY Signal Analyzer")

# === UI Filters ===
signal_list = ["Any"] + sorted(summary["Signal"].dropna().unique())
candle_list = ["Any"] + sorted(summary["Candles"].dropna().unique())
signal = st.selectbox("Select Signal", signal_list)
candle_type = st.selectbox("Candle Type", candle_list)

# Prev_Move filter
if "Prev_Move" in summary.columns:
    label_mapping = {
        "Very Strong Long": "Very Strong Long (>= 1.00%)",
        "Moderate Long": "Moderate Long (0.40% to 1.00%)",
        "Sideways": "Sideways (-0.40% to +0.40%)",
        "Moderate Short": "Moderate Short (-0.40% to -1.00%)",
        "Very Strong Short": "Very Strong Short (<= -1.00%)"
    }
    raw = summary["Prev_Move"].dropna().unique()
    opts = ["Any"] + [label_mapping[val] for val in raw if val in label_mapping]
    selected_prev = st.selectbox("Previous Day View", opts)

# === Initial Filtering ===
filtered = summary.copy()
if signal != "Any":
    filtered = filtered[filtered["Signal"] == signal]
if candle_type != "Any":
    filtered = filtered[filtered["Candles"] == candle_type]
if "Prev_Move" in summary.columns and selected_prev != "Any":
    rev_map = {v: k for k, v in label_mapping.items()}
    base = rev_map[selected_prev]
    filtered = filtered[filtered["Prev_Move"] == base]

# === 5-Min Confirmation ===
st.markdown("### 5-Min Confirmation (Optional)")
enable_5 = st.checkbox("Enable 5-min candle condition")
breakout_moves_5 = {}
if enable_5:
    logic_5 = st.radio("Condition", [
        "Close Above First 30-min High",
        "Close Below First 30-min Low",
        "No Breakout (Neither Above Nor Below)"
    ])
    nums_5 = st.multiselect(
        "5-min Candle Numbers (starting from 2nd)",
        options=list(range(2, 10)), default=[2]
    )
    valid_5 = []
    missing_5 = []
    for day in filtered["date"].unique():
        if day not in available_5min_dates:
            missing_5.append(day)
            continue
        day30 = df_30min[df_30min["date"] == day]
        if day30.empty:
            continue
        high30 = day30.iloc[0]["high"]
        low30 = day30.iloc[0]["low"]

        day5 = df_5min[df_5min["date"] == day].reset_index(drop=True)
        idxs = [i-1 for i in nums_5 if i-1 < len(day5)]
        window5 = day5.iloc[idxs]

        cond = False
        breakout = None
        if logic_5 == "No Breakout (Neither Above Nor Below)":
            if window5["close"].le(high30).all() and window5["close"].ge(low30).all():
                cond = True
                breakout = window5.iloc[0]
        else:
            op = window5["close"] > high30 if logic_5.startswith("Close Above") else window5["close"] < low30
            hits = window5[op]
            if not hits.empty:
                cond = True
                breakout = hits.iloc[0]

        if cond:
            valid_5.append(day)
            if breakout is not None:
                last = day5.iloc[-1]["close"]
                breakout_moves_5[day] = round(last - breakout["close"], 2)

    st.info(f"Out of {len(filtered)} days, {len(valid_5)} passed 5-min confirmation.")
    if missing_5:
        st.warning(f"{len(missing_5)} days missing 5-min data.")
    filtered = filtered[filtered["date"].isin(valid_5)]
    if breakout_moves_5:
        filtered["5_Move"] = filtered["date"].map(breakout_moves_5)

# === 30-Min Confirmation ===
st.markdown("### 30-Min Confirmation (Optional)")
enable_30 = st.checkbox("Enable 30-min candle condition")
breakout_moves_30 = {}
if enable_30:
    logic_30 = st.radio("30-Min Condition", [
        "Close Above First 30-min High",
        "Close Below First 30-min Low",
        "No Breakout (Neither Above Nor Below)",
        "Goes Above Close Below",
        "Goes Below Close Above"
    ])
    nums_30 = st.multiselect(
        "30-min Candle Numbers (starting from 2nd)",
        options=list(range(2, 10)), default=[2]
    )
    valid_30 = []
    missing_30 = []
    for day in filtered["date"].unique():
        if day not in available_30min_dates:
            missing_30.append(day)
            continue
        day30 = df_30min[df_30min["date"] == day].reset_index(drop=True)
        if day30.empty:
            continue
        first = day30.iloc[0]
        h0, l0 = first["high"], first["low"]
        idxs = [i-1 for i in nums_30 if i-1 < len(day30)]
        window30 = day30.iloc[idxs]

        cond = False
        breakout = None
        for _, row in window30.iterrows():
            if logic_30 == "No Breakout (Neither Above Nor Below)":
                if window30["close"].le(h0).all() and window30["close"].ge(l0).all():
                    cond = True
                    breakout = window30.iloc[0]
                    break
            elif logic_30 == "Close Above First 30-min High" and row["close"] > h0:
                cond, breakout = True, row; break
            elif logic_30 == "Close Below First 30-min Low" and row["close"] < l0:
                cond, breakout = True, row; break
            elif logic_30 == "Goes Above Close Below" and row["high"] > h0 and row["close"] < h0:
                cond, breakout = True, row; break
            elif logic_30 == "Goes Below Close Above" and row["low"] < l0 and row["close"] > l0:
                cond, breakout = True, row; break

        if cond:
            valid_30.append(day)
            if breakout is not None:
                last = day30.iloc[-1]["close"]
                breakout_moves_30[day] = round(last - breakout["close"], 2)

    st.info(f"Out of {len(filtered)} days, {len(valid_30)} passed 30-min confirmation.")
    if missing_30:
        st.warning(f"{len(missing_30)} days missing 30-min data.")
    filtered = filtered[filtered["date"].isin(valid_30)]
    if breakout_moves_30:
        filtered["30_Move"] = filtered["date"].map(breakout_moves_30)

# === Results Summary and Charting ===
st.markdown(f"### Filtered Results: {len(filtered)} Days Matched")
if not filtered.empty:
    counts = filtered["Move.1"].value_counts()
    longs = counts.get("Long", 0); shorts = counts.get("Short", 0)
    total = longs + shorts
    st.write(f"Long: {longs} ({longs/total*100:.2f}%); Short: {shorts} ({shorts/total*100:.2f}%)")

    if "Move" in filtered.columns:
        st.markdown("### Move in Points")
        st.write(f"Avg Move: {filtered['Move'].abs().mean():.2f} pts")
        st.write(f"Max: {filtered['Move'].max():.2f} pts; Min: {filtered['Move'].min():.2f} pts")

    # Display table
    disp = filtered.copy()
    disp["Date"] = pd.to_datetime(disp["date"]).dt.strftime("%d %b, %y")
    cols = ["Date", "Signal", "Candles", "Move.1", "Move"]
    if "5_Move" in disp: cols.append("5_Move")
    if "30_Move" in disp: cols.append("30_Move")
    if "Prev_Move" in disp: cols.append("Prev_Move")
    st.dataframe(disp[cols].sort_values(by="Date", ascending=False))

    # Accuracy breakdown
    st.markdown("### Periodic Accuracy Breakdown")
    period = st.selectbox("Group By", ["Month", "Quarter", "Year"], index=2)
    dfp = filtered.copy()
    dfp["Date"] = pd.to_datetime(dfp["date"])
    if period == "Month": dfp["Period"] = dfp["Date"].dt.to_period("M").astype(str)
    elif period == "Quarter": dfp["Period"] = dfp["Date"].dt.to_period("Q").astype(str)
    else: dfp["Period"] = dfp["Date"].dt.year.astype(str)

    pivot = dfp.groupby("Period")["Move.1"].value_counts().unstack(fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    pivot["Long %"] = (pivot.get("Long",0)/pivot["Total"]*100).round(2)
    pivot["Short %"] = (pivot.get("Short",0)/pivot["Total"]*100).round(2)
    st.dataframe(pivot[["Long","Short","Total","Long %","Short %"]].sort_index())

    # Chart
    st.markdown("### Accuracy Chart")
    fig, ax = plt.subplots()
    pivot[["Long %","Short %"]].plot(kind="bar", ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Accuracy (%)")
    plt.title(f"{period}ly Accuracy")
    st.pyplot(fig)
else:
    st.warning("No matching data found.")
