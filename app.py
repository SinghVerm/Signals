import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# === Load Data ===
@st.cache_data
def load_data():
    # Daily summary
    summary = pd.read_excel("Daily_Summary_with_Prioritized_Signal.xlsx")
    summary.columns = summary.columns.str.strip()
    summary["Date"] = pd.to_datetime(summary["Date"], dayfirst=True)
    summary["date"] = summary["Date"].dt.date

    # 30-min and 5-min data
    df_30 = pd.read_csv("NSE_NIFTY, 30.csv", parse_dates=["time"])
    df_5  = pd.read_csv("NIFTY_5min_All_Sorted.csv", parse_dates=["time"])
    df_30["date"] = df_30["time"].dt.date
    df_5["date"]  = df_5["time"].dt.date

    return summary, df_30, df_5

summary, df_30min, df_5min = load_data()
available_5min  = set(df_5min["date"])
available_30min = set(df_30min["date"])

# === App Title ===
st.title("NIFTY Signal Analyzer")

# === Summary Filters ===
signal_opts = ["Any"] + sorted(summary["Signal"].dropna().unique())
candle_opts = ["Any"] + sorted(summary["Candles"].dropna().unique())
signal      = st.selectbox("Select Signal", signal_opts)
candle_type = st.selectbox("Candle Type", candle_opts)

# Previous Day Move filter
if "Prev_Move" in summary.columns:
    move_map   = {
        "Very Strong Long": "Very Strong Long (>= 1.00%)",
        "Moderate Long":    "Moderate Long (0.40% to 1.00%)",
        "Sideways":         "Sideways (-0.40% to +0.40%)",
        "Moderate Short":   "Moderate Short (-0.40% to -1.00%)",
        "Very Strong Short":"Very Strong Short (<= -1.00%)"
    }
    prev_opts    = ["Any"] + [move_map[v] for v in summary["Prev_Move"].dropna().unique() if v in move_map]
    selected_prev= st.selectbox("Previous Day Move", prev_opts)

# Apply summary-level filtering
filtered = summary.copy()
if signal != "Any":
    filtered = filtered[filtered["Signal"] == signal]
if candle_type != "Any":
    filtered = filtered[filtered["Candles"] == candle_type]
if "Prev_Move" in summary.columns and selected_prev != "Any":
    inv_map = {v: k for k, v in move_map.items()}
    filtered = filtered[filtered["Prev_Move"] == inv_map[selected_prev]]

# === 5-Min Confirmation ===
st.markdown("### 5-Min Confirmation (Optional)")
enable_5 = st.checkbox("Enable 5-min breakout check")
breakout_5 = {}
if enable_5:
    logic_5 = st.radio("Condition", [
        "Close Above First 30-min High",
        "Close Below First 30-min Low",
        "No Breakout (Neither)"
    ])
    valid_5, missing_5 = [], []
    for day in filtered["date"].unique():
        if day not in available_5min:
            missing_5.append(day)
            continue
        day30 = df_30min[df_30min["date"] == day]
        if day30.empty:
            continue
        h30 = day30.iloc[0]["high"]
        l30 = day30.iloc[0]["low"]

        day5 = (df_5min[df_5min["date"] == day]
                .sort_values("time").reset_index(drop=True))
        window5 = day5.iloc[6:12]  # 6 bars: 9:45–10:10

        meets, hit = False, None
        if logic_5 == "Close Above First 30-min High":
            hits = window5[window5["close"] > h30]
            if not hits.empty:
                meets, hit = True, hits.iloc[0]
        elif logic_5 == "Close Below First 30-min Low":
            hits = window5[window5["close"] < l30]
            if not hits.empty:
                meets, hit = True, hits.iloc[0]
        else:
            if window5["close"].le(h30).all() and window5["close"].ge(l30).all():
                meets, hit = True, window5.iloc[0]

        if meets:
            valid_5.append(day)
            last_close = day5.iloc[-1]["close"]
            breakout_5[day] = round((last_close - hit["close"]) if hit is not None else 0, 2)

    st.info(f"Out of {len(filtered)} days, {len(valid_5)} passed 5-min check.")
    if missing_5:
        st.warning(f"{len(missing_5)} days missing 5-min data.")
    filtered = filtered[filtered["date"].isin(valid_5)]
    if breakout_5:
        filtered["5_Move"] = filtered["date"].map(breakout_5)

# === 30-Min Flag Filter ===
st.markdown("### 30-Min Flag Filter (Optional)")
enable_30 = st.checkbox("Enable 30-min flag filter")
if enable_30:
    level  = st.selectbox("Which level?", ["Any", "High", "Mid", "Yesterday Low"])
    result = st.selectbox("Result",      ["Any", "Touch & Close Above", "Touch & Close Below", "No Touch"])
    if level != "Any" and result != "Any":
        mask       = df_30min[level] == result
        good_dates = df_30min.loc[mask, "date"].unique()
        filtered   = filtered[filtered["date"].isin(good_dates)]

# === Results & Chart ===
st.markdown(f"### Filtered Results: {len(filtered)} Days Matched")
if filtered.empty:
    st.warning("No matching data found.")
else:
    cnt    = filtered["Move.1"].value_counts()
    longs  = cnt.get("Long", 0)
    shorts = cnt.get("Short", 0)
    total  = longs + shorts
    st.write(f"Long: {longs} ({(longs/total*100) if total else 0:.2f}%) | "
             f"Short: {shorts} ({(shorts/total*100) if total else 0:.2f}%)")

    # Move stats
    if "Move" in filtered.columns:
        st.markdown("#### Move in Points")
        st.write(f"Avg: {filtered['Move'].abs().mean():.2f} pts; "
                 f"Max: {filtered['Move'].max():.2f} pts; "
                 f"Min: {filtered['Move'].min():.2f} pts")

    # Display table sorted newest-first
    disp = filtered.sort_values(by="date", ascending=False).copy()
    disp["Date"] = pd.to_datetime(disp["date"]).dt.strftime("%d %b, %y")
    base_cols = ["Date", "Signal", "Candles", "Move.1", "Move"]
    flag_cols = [c for c in ["High", "Mid", "Yesterday Low"] if c in disp.columns]
    extra     = (["5_Move"] if "5_Move" in disp.columns else []) + \
                (["Prev_Move"] if "Prev_Move" in disp.columns else [])
    st.dataframe(disp[base_cols + flag_cols + extra].reset_index(drop=True))

    # Periodic breakdown
    st.markdown("#### Periodic Accuracy Breakdown")
    period = st.selectbox("Group By", ["Month", "Quarter", "Year"], index=2)
    dfp    = filtered.copy()
    dfp["Date"] = pd.to_datetime(dfp["date"])
    if period == "Month":
        dfp["Period"] = dfp["Date"].dt.to_period("M").astype(str)
    elif period == "Quarter":
        dfp["Period"] = dfp["Date"].dt.to_period("Q").astype(str)
    else:
        dfp["Period"] = dfp["Date"].dt.year.astype(str)
    pivot = dfp.groupby("Period")["Move.1"].value_counts().unstack(fill_value=0)
    pivot["Total"]   = pivot.sum(axis=1)
    pivot["Long %"]  = (pivot.get("Long", 0)  / pivot["Total"] * 100).round(2)
    pivot["Short %"] = (pivot.get("Short", 0) / pivot["Total"] * 100).round(2)
    st.dataframe(pivot[["Long", "Short", "Total", "Long %", "Short %"]].sort_index())

    # Accuracy chart
    st.markdown("#### Accuracy Chart")
    fig, ax = plt.subplots()
    pivot[["Long %", "Short %"]].plot(kind="bar", ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Accuracy (%)")
    plt.title(f"{period}ly Accuracy")
    st.pyplot(fig)
