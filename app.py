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

    df_30["date"] = df_30["time"].dt.date
    df_5["date"] = df_5["time"].dt.date
    summary["Date"] = pd.to_datetime(summary["Date"], dayfirst=True)
    summary["date"] = summary["Date"].dt.date
    return summary, df_30, df_5

# Prepare data
summary, df_30min, df_5min = load_data()
available_5min_dates = set(df_5min["date"].unique())
available_30min_dates = set(df_30min["date"].unique())

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
    opts = ["Any"] + [label_mapping[v] for v in summary["Prev_Move"].dropna().unique() if v in label_mapping]
    selected_prev = st.selectbox("Previous Day View", opts)

# Base filtering
filtered = summary.copy()
if signal != "Any": filtered = filtered[filtered["Signal"] == signal]
if candle_type != "Any": filtered = filtered[filtered["Candles"] == candle_type]
if "Prev_Move" in summary.columns and selected_prev != "Any":
    rev = {v:k for k,v in label_mapping.items()}
    filtered = filtered[filtered["Prev_Move"] == rev[selected_prev]]

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
    valid_5, missing_5 = [], []
    for day in filtered["date"].unique():
        if day not in available_5min_dates:
            missing_5.append(day)
            continue
        # first 30-min high/low
        first30 = df_30min[df_30min["date"] == day].iloc[0]
        h30, l30 = first30["high"], first30["low"]
        # next six 5-min bars (9:45–10:10)
        day5 = df_5min[df_5min["date"] == day].sort_values("time").reset_index(drop=True)
        window5 = day5.iloc[6:12]
        if window5.empty:
            continue
        cond, br = False, None
        if logic_5 == "Close Above First 30-min High":
            hits = window5[window5["close"] > h30]
            if not hits.empty: cond, br = True, hits.iloc[0]
        elif logic_5 == "Close Below First 30-min Low":
            hits = window5[window5["close"] < l30]
            if not hits.empty: cond, br = True, hits.iloc[0]
        else:
            if window5["close"].le(h30).all() and window5["close"].ge(l30).all():
                cond, br = True, window5.iloc[0]
        if cond:
            valid_5.append(day)
            last_close = day5.iloc[-1]["close"]
            breakout_moves_5[day] = round(last_close - br["close"], 2) if br is not None else 0
    st.info(f"Out of {len(filtered)} days, {len(valid_5)} passed 5-min confirmation.")
    if missing_5: st.warning(f"{len(missing_5)} days missing 5-min data.")
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
