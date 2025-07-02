import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

@st.cache_data
def load_data():
    summary = pd.read_excel("Daily_Summary_with_Prioritized_Signal.xlsx")
    summary.columns = summary.columns.str.strip()
    df_30 = pd.read_csv("NSE_NIFTY, 30.csv", parse_dates=["time"])
    df_5 = pd.read_csv("NIFTY_5min_All_Sorted.csv", parse_dates=["time"])

    df_30['date'] = df_30['time'].dt.date
    df_5['date'] = df_5['time'].dt.date
    summary['Date'] = pd.to_datetime(summary['Date'], dayfirst=True)
    summary['date'] = summary['Date'].dt.date
    return summary, df_30, df_5

summary, df_30min, df_5min = load_data()
available_5min = set(df_5min['date'].unique())
available_30min = set(df_30min['date'].unique())

st.title("NIFTY Signal Analyzer")

# === Summary Filters
signal_opts = ["Any"] + sorted(summary["Signal"].dropna().unique())
candle_opts = ["Any"] + sorted(summary["Candles"].dropna().unique())
signal = st.selectbox("Select Signal", signal_opts)
candle_type = st.selectbox("Candle Type", candle_opts)

if "Prev_Move" in summary.columns:
    move_map = {
        "Very Strong Long": "Very Strong Long (>= 1.00%)",
        "Moderate Long": "Moderate Long (0.40% to 1.00%)",
        "Sideways": "Sideways (-0.40% to +0.40%)",
        "Moderate Short": "Moderate Short (-0.40% to -1.00%)",
        "Very Strong Short": "Very Strong Short (<= -1.00%)"
    }
    move_opts = ["Any"] + [move_map[m] for m in summary["Prev_Move"].dropna().unique() if m in move_map]
    selected_prev = st.selectbox("Previous Day Move", move_opts)

filtered = summary.copy()
if signal != "Any":
    filtered = filtered[filtered["Signal"] == signal]
if candle_type != "Any":
    filtered = filtered[filtered["Candles"] == candle_type]
if "Prev_Move" in summary.columns and selected_prev != "Any":
    inv_map = {v: k for k, v in move_map.items()}
    filtered = filtered[filtered["Prev_Move"] == inv_map[selected_prev]]

# === 5-Min Confirmation ===
st.markdown("### 5-Min Confirmation")
enable_5 = st.checkbox("Enable 5-min candle confirmation")
breakout_5 = {}
if enable_5:
    logic_5 = st.radio("5-min Condition", [
        "Close Above First 30-min High",
        "Close Below First 30-min Low",
        "No Breakout (Neither)"
    ])
    valid_5, missing_5 = [], []
    for day in filtered["date"].unique():
        if day not in available_5min:
            missing_5.append(day)
            continue
        df30 = df_30min[df_30min["date"] == day]
        if df30.empty:
            continue
        h30 = df30.iloc[0]["high"]
        l30 = df30.iloc[0]["low"]
        df5 = df_5min[df_5min["date"] == day].sort_values("time").reset_index(drop=True)
        window = df5.iloc[6:12]
        match = False
        candle = None
        if logic_5 == "Close Above First 30-min High":
            hit = window[window["close"] > h30]
            if not hit.empty:
                match = True
                candle = hit.iloc[0]
        elif logic_5 == "Close Below First 30-min Low":
            hit = window[window["close"] < l30]
            if not hit.empty:
                match = True
                candle = hit.iloc[0]
        else:
            if window["close"].le(h30).all() and window["close"].ge(l30).all():
                match = True
                candle = window.iloc[0]
        if match:
            valid_5.append(day)
            if candle is not None:
                last_close = df5.iloc[-1]["close"]
                breakout_5[day] = round(last_close - candle["close"], 2)
    st.info(f"{len(valid_5)} / {len(filtered)} passed 5-min confirmation.")
    if missing_5:
        st.warning(f"{len(missing_5)} missing 5-min data.")
    filtered = filtered[filtered["date"].isin(valid_5)]
    if breakout_5:
        filtered["5_Move"] = filtered["date"].map(breakout_5)
# === 30-Min Breakout Confirmation (Original Logic)
st.markdown("### 30-Min Confirmation (Original)")
enable_30 = st.checkbox("Enable 30-min candle condition")

breakout_30 = {}
if enable_30:
    logic_30 = st.radio("30-min Condition", [
        "Close Above First 30-min High",
        "Close Below First 30-min Low",
        "No Breakout (Neither)",
        "Goes Above Close Below",
        "Goes Below Close Above"
    ])
    candle_nums = st.multiselect("30-min Candle Numbers (starting from 2nd)", list(range(2, 10)), default=[2])
    valid_30, missing_30 = [], []

    for day in filtered["date"].unique():
        df_day = df_30min[df_30min["date"] == day]
        if df_day.empty:
            missing_30.append(day)
            continue
        high = df_day.iloc[0]["high"]
        low = df_day.iloc[0]["low"]
        df_window = df_day.reset_index(drop=True).iloc[[i - 1 for i in candle_nums if i - 1 < len(df_day)]]

        match = False
        candle = None
        for _, row in df_window.iterrows():
            c_high, c_low, c_close = row["high"], row["low"], row["close"]
            if logic_30 == "Close Above First 30-min High" and c_close > high:
                match = True; candle = row; break
            elif logic_30 == "Close Below First 30-min Low" and c_close < low:
                match = True; candle = row; break
            elif logic_30 == "No Breakout (Neither)":
                if (df_window["close"] <= high).all() and (df_window["close"] >= low).all():
                    match = True; candle = df_window.iloc[0]; break
            elif logic_30 == "Goes Above Close Below" and c_high > high and c_close < high:
                match = True; candle = row; break
            elif logic_30 == "Goes Below Close Above" and c_low < low and c_close > low:
                match = True; candle = row; break

        if match:
            valid_30.append(day)
            if candle is not None:
                last_close = df_day.iloc[-1]["close"]
                breakout_30[day] = round(last_close - candle["close"], 2)

    st.info(f"{len(valid_30)} / {len(filtered)} matched 30-min condition.")
    if missing_30:
        st.warning(f"{len(missing_30)} missing 30-min data.")
    filtered = filtered[filtered["date"].isin(valid_30)]
    if breakout_30:
        filtered["30_Move"] = filtered["date"].map(breakout_30)

# === New: 30-Min Flag Filter
st.markdown("### 30-Min Flag Filter (Enriched Columns)")
enable_flag = st.checkbox("Enable flag-based filter (High/Mid/Low)")

if enable_flag:
    level = st.selectbox("Touch Level", ["Any", "High", "Mid", "Yesterday Low"])
    condition = st.selectbox("Touch Result", ["Any", "Touch & Close Above", "Touch & Close Below", "No Touch"])
    flag_candles = st.multiselect("30-min Candles to check", list(range(1, 10)), default=[2])

    if level != "Any" and condition != "Any":
        valid_flags = []
        for day in filtered["date"].unique():
            df_day = df_30min[df_30min["date"] == day].reset_index(drop=True)
            indices = [i - 1 for i in flag_candles if 0 <= i - 1 < len(df_day)]
            df_slice = df_day.iloc[indices]
            if any(df_slice[level] == condition):
                valid_flags.append(day)
        filtered = filtered[filtered["date"].isin(valid_flags)]
# === Results Summary
st.markdown(f"### Filtered Results: {len(filtered)} Days Matched")

if filtered.empty:
    st.warning("No matching data found.")
else:
    # Signal direction breakdown
    counts = filtered["Move.1"].value_counts()
    longs = counts.get("Long", 0)
    shorts = counts.get("Short", 0)
    total = longs + shorts
    long_pct = (longs / total * 100) if total else 0
    short_pct = (shorts / total * 100) if total else 0

    st.write(f"Long: {longs} ({long_pct:.2f}%) | Short: {shorts} ({short_pct:.2f}%)")

    # Move stats
    if "Move" in filtered.columns:
        st.markdown("### Move in Points")
        st.write(f"Avg Abs Move: {filtered['Move'].abs().mean():.2f} pts")
        st.write(f"Max Move: {filtered['Move'].max():.2f} pts")
        st.write(f"Min Move: {filtered['Move'].min():.2f} pts")

    # Prepare DataFrame for display
    disp = filtered.sort_values(by="date", ascending=False).copy()
    disp["Date"] = pd.to_datetime(disp["Date"]).dt.strftime("%d %b, %y")
    cols = ["Date", "Signal", "Candles", "Move.1", "Move"]

    # Optional columns
    if "Prev_Move" in disp.columns:
        cols.append("Prev_Move")
    for flag_col in ["High", "Mid", "Yesterday Low"]:
        if flag_col in disp.columns:
            cols.append(flag_col)
    if "5_Move" in disp.columns:
        cols.append("5_Move")
    if "30_Move" in disp.columns:
        cols.append("30_Move")

    st.dataframe(disp[cols].reset_index(drop=True))

    # === Periodic Accuracy Breakdown
    st.markdown("### Periodic Accuracy Breakdown")
    group_by = st.selectbox("Group By", ["Month", "Quarter", "Year"], index=2)

    dfp = filtered.copy()
    dfp["Date"] = pd.to_datetime(dfp["date"])
    if group_by == "Month":
        dfp["Period"] = dfp["Date"].dt.to_period("M").astype(str)
    elif group_by == "Quarter":
        dfp["Period"] = dfp["Date"].dt.to_period("Q").astype(str)
    else:
        dfp["Period"] = dfp["Date"].dt.year.astype(str)

    pivot = dfp.groupby("Period")["Move.1"].value_counts().unstack(fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    pivot["Long %"] = (pivot.get("Long", 0) / pivot["Total"] * 100).round(2)
    pivot["Short %"] = (pivot.get("Short", 0) / pivot["Total"] * 100).round(2)

    st.dataframe(pivot[["Long", "Short", "Total", "Long %", "Short %"]].sort_index())

    # Accuracy Chart
    st.markdown("### Accuracy Chart")
    fig, ax = plt.subplots()
    pivot[["Long %", "Short %"]].plot(kind="bar", ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Accuracy (%)")
    plt.title(f"{group_by}ly Accuracy")
    st.pyplot(fig)
