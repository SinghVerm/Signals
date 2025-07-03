# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

@st.cache_data
def load_data():
    summary = pd.read_excel("Daily_Summary_with_Prioritized_Signal.xlsx")
    summary.columns = summary.columns.str.strip()
    df_30 = pd.read_csv("NSE_NIFTY, 30.csv", parse_dates=["time"])
    df_5 = pd.read_csv("NIFTY_5min_All_Sorted.csv", parse_dates=["time"])
    summary["Date"] = pd.to_datetime(summary["Date"], dayfirst=True)
    summary["date"] = summary["Date"].dt.date
    df_30["date"] = df_30["time"].dt.date
    df_5["date"] = df_5["time"].dt.date
    return summary, df_30, df_5

summary, df_30min, df_5min = load_data()
available_5min = set(df_5min["date"].unique())
available_30min = set(df_30min["date"].unique())

st.set_page_config(layout="wide")
st.title("📊 NIFTY Signal Analyzer")

# === Summary Filters
with st.expander("🔍 Filter Summary Data", expanded=True):
    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        signal_opts = ["Any"] + sorted(summary["Signal"].dropna().unique())
        signal = st.selectbox("Select Signal", signal_opts)
    with colf2:
        candle_opts = ["Any"] + sorted(summary["Candles"].dropna().unique())
        candle_type = st.selectbox("Candle Type", candle_opts)
    with colf3:
        selected_prev = "Any"
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
if selected_prev != "Any":
    inv_map = {v: k for k, v in move_map.items()}
    filtered = filtered[filtered["Prev_Move"] == inv_map[selected_prev]]

# === Load and Display Entry/Exit Rules for Selected Signal
try:
    df_rules = pd.read_excel("Signals.xlsx")
    df_rules.columns = df_rules.columns.str.strip()
    df_rules["Signal"] = df_rules["Signal"].ffill().astype(str).str.strip()
    df_rules["View"] = df_rules["View"].ffill().astype(str).str.strip().str.lower()

    if signal != "Any":
        matched_rows = df_rules[df_rules["Signal"] == signal]
        if not matched_rows.empty:
            with st.expander("📘 Entry & Exit Rules", expanded=True):
                for view_label, color in [("long", "limegreen"), ("short", "red")]:
                    view_rows = matched_rows[matched_rows["View"] == view_label]
                    if not view_rows.empty:
                        st.markdown(f"<span style='color:{color}; font-weight:bold'>🔹 {view_label.capitalize()} View</span>", unsafe_allow_html=True)
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Entry Rules:**")
                            for entry in view_rows["Entry"].dropna():
                                st.markdown(f"- {entry.strip()}")

                        with col2:
                            st.markdown("**Exit Rules:**")
                            for exit_rule in view_rows["Exit"].dropna():
                                st.markdown(f"- {exit_rule.strip()}")
except Exception as e:
    st.warning(f"Could not load rules: {e}")


# === Signal Confirmation Filters
colc1, colc2 = st.columns(2)
with colc1:
    with st.expander("🕐 5-Min Confirmation"):
        enable_5 = st.checkbox("Enable 5-min confirmation")
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
                df30 = df_30min[df_30min["date"] == day]
                if df30.empty: continue
                h30, l30 = df30.iloc[0]["high"], df30.iloc[0]["low"]
                df5 = df_5min[df_5min["date"] == day].sort_values("time").reset_index(drop=True)
                window = df5.iloc[6:12]
                match = False; candle = None
                if logic_5 == "Close Above First 30-min High":
                    hit = window[window["close"] > h30]
                    if not hit.empty: match = True; candle = hit.iloc[0]
                elif logic_5 == "Close Below First 30-min Low":
                    hit = window[window["close"] < l30]
                    if not hit.empty: match = True; candle = hit.iloc[0]
                else:
                    if window["close"].le(h30).all() and window["close"].ge(l30).all():
                        match = True; candle = window.iloc[0]
                if match:
                    valid_5.append(day)
                    last_close = df5.iloc[-1]["close"]
                    breakout_5[day] = round(last_close - candle["close"], 2)
            filtered = filtered[filtered["date"].isin(valid_5)]
            if breakout_5:
                filtered["5_Move"] = filtered["date"].map(breakout_5)
            st.info(f"{len(valid_5)} passed, {len(missing_5)} missing 5-min data")

with colc2:
    with st.expander("🕐 30-Min Confirmation"):
        enable_30 = st.checkbox("Enable 30-min confirmation")
        breakout_30 = {}
        if enable_30:
            logic_30 = st.radio("Condition", [
                "Close Above First 30-min High",
                "Close Below First 30-min Low",
                "No Breakout (Neither)",
                "Goes Above Close Below",
                "Goes Below Close Above"
            ])
            candle_nums = st.multiselect("Candle Numbers (from 2nd)", list(range(2, 10)), default=[2])
            valid_30, missing_30 = [], []
            for day in filtered["date"].unique():
                df_day = df_30min[df_30min["date"] == day]
                if df_day.empty:
                    missing_30.append(day)
                    continue
                high, low = df_day.iloc[0]["high"], df_day.iloc[0]["low"]
                df_window = df_day.reset_index(drop=True).iloc[[i - 1 for i in candle_nums if i - 1 < len(df_day)]]
                match = False; candle = None
                for _, row in df_window.iterrows():
                    ch, cl, cc = row["high"], row["low"], row["close"]
                    if logic_30 == "Close Above First 30-min High" and cc > high:
                        match = True; candle = row; break
                    elif logic_30 == "Close Below First 30-min Low" and cc < low:
                        match = True; candle = row; break
                    elif logic_30 == "No Breakout (Neither)":
                        if (df_window["close"] <= high).all() and (df_window["close"] >= low).all():
                            match = True; candle = df_window.iloc[0]; break
                    elif logic_30 == "Goes Above Close Below" and ch > high and cc < high:
                        match = True; candle = row; break
                    elif logic_30 == "Goes Below Close Above" and cl < low and cc > low:
                        match = True; candle = row; break
                if match:
                    valid_30.append(day)
                    last_close = df_day.iloc[-1]["close"]
                    breakout_30[day] = round(last_close - candle["close"], 2)
            filtered = filtered[filtered["date"].isin(valid_30)]
            if breakout_30:
                filtered["30_Move"] = filtered["date"].map(breakout_30)
            st.info(f"{len(valid_30)} passed, {len(missing_30)} missing 30-min data")

# === Flag and Untouched Filters
colf1, colf2 = st.columns(2)

with colf1:
    with st.expander("📊 30M Above/Below"):
        enable_flag = st.checkbox("Enable Flag Filter")
        if enable_flag:
            level = st.selectbox("Level", ["Any", "High", "Mid", "Low"], key="flag_level")
            condition = st.selectbox("Result", ["Any", "Touch & Close Above", "Touch & Close Below", "No Touch"], key="flag_result")
            flag_candles = st.multiselect("Candle Numbers", list(range(1, 10)), default=[2], key="flag_candles")
            if level != "Any" and condition != "Any":
                valid_flags = []
                for day in filtered["date"].unique():
                    df_day = df_30min[df_30min["date"] == day].reset_index(drop=True)
                    indices = [i - 1 for i in flag_candles if 0 <= i - 1 < len(df_day)]
                    df_slice = df_day.iloc[indices]
                    if any(df_slice[level] == condition):
                        valid_flags.append(day)
                filtered = filtered[filtered["date"].isin(valid_flags)]

with colf2:
    with st.expander("📊 Untouched Filter"):
        enable_untouched = st.checkbox("Enable Untouched Filter")
        if enable_untouched:
            level = st.selectbox("Untouched Level", ["Any", "Untouched High", "Untouched Mid", "Untouched Low"], key="untouched_level")
            condition = st.selectbox("Result", ["Any", "Touch & Close Above", "Touch & Close Below", "No Touch"], key="untouched_result")
            untouched_candles = st.multiselect("Candle Numbers", list(range(1, 10)), default=[2], key="untouched_candles")
            if level != "Any" and condition != "Any":
                valid_flags = []
                for day in filtered["date"].unique():
                    df_day = df_30min[df_30min["date"] == day].reset_index(drop=True)
                    indices = [i - 1 for i in untouched_candles if 0 <= i - 1 < len(df_day)]
                    df_slice = df_day.iloc[indices]
                    if any(df_slice[level] == condition):
                        valid_flags.append(day)
                filtered = filtered[filtered["date"].isin(valid_flags)]


# === Results Section
st.markdown(f"### ✅ Filtered Results: {len(filtered)} Days")

if filtered.empty:
    st.warning("No matching data found.")
else:
    counts = filtered["Move.1"].value_counts()
    longs, shorts = counts.get("Long", 0), counts.get("Short", 0)
    total = longs + shorts
    long_pct = (longs / total * 100) if total else 0
    short_pct = (shorts / total * 100) if total else 0
    diff = abs(long_pct - short_pct)

    if diff < 15:
        long_color = short_color = "gold"
    else:
        long_color = "limegreen" if long_pct > short_pct else "gray"
        short_color = "red" if short_pct > long_pct else "gray"

    st.markdown(
        f"<span style='color:{long_color}; font-weight:bold'>Long: {longs} ({long_pct:.2f}%)</span> | "
        f"<span style='color:{short_color}; font-weight:bold'>Short: {shorts} ({short_pct:.2f}%)</span>",
        unsafe_allow_html=True
    )


    if "Move" in filtered.columns:
        st.markdown("### Move Stats")
        st.write(f"Avg Abs Move: {filtered['Move'].abs().mean():.2f} pts")
        st.write(f"Max Move: {filtered['Move'].max():.2f} pts")
        st.write(f"Min Move: {filtered['Move'].min():.2f} pts")

    disp = filtered.sort_values("date", ascending=False).copy()
    disp["Date"] = pd.to_datetime(disp["Date"]).dt.strftime("%d %b, %y")
    cols = ["Date", "Signal", "Candles", "Move.1", "Move"]
    for c in ["Prev_Move", "High", "Mid", "Low", "Untouched High", "Untouched Mid", "Untouched Low", "5_Move", "30_Move"]:
        if c in disp.columns:
            cols.append(c)
    st.dataframe(disp[cols].reset_index(drop=True))


    # === Accuracy by Period
with st.expander("📈 Periodic Accuracy Breakdown"):
    group_by = st.selectbox("Group By", ["Month", "Quarter", "Year"], index=2)
    dfp = filtered.copy()
    dfp["Date"] = pd.to_datetime(dfp["date"])

    # Period column logic
    if group_by == "Month":
        dfp["Period"] = dfp["Date"].dt.to_period("M").astype(str)
    elif group_by == "Quarter":
        dfp["Period"] = dfp["Date"].dt.to_period("Q").astype(str)
    else:
        dfp["Period"] = dfp["Date"].dt.year.astype(str)

    pivot = dfp.groupby("Period")["Move.1"].value_counts().unstack(fill_value=0)

    if pivot.empty or pivot.sum(axis=1).sum() == 0:
        st.info("ℹ️ Not enough data to display period breakdown.")
    else:
        pivot["Total"] = pivot.sum(axis=1)
        pivot["Long %"] = (pivot.get("Long", 0) / pivot["Total"] * 100).round(2)
        pivot["Short %"] = (pivot.get("Short", 0) / pivot["Total"] * 100).round(2)

        # Show only available columns
        display_cols = ["Total", "Long %", "Short %"]
        if "Long" in pivot.columns:
            display_cols.insert(0, "Long")
        if "Short" in pivot.columns:
            display_cols.insert(1 if "Long" in display_cols else 0, "Short")

        st.dataframe(pivot[display_cols].sort_index())

        st.markdown("### 📊 Accuracy Chart")
        fig, ax = plt.subplots()
        pivot[["Long %", "Short %"]].plot(kind="bar", ax=ax)
        plt.xticks(rotation=45)
        plt.ylabel("Accuracy (%)")
        plt.title(f"{group_by}ly Accuracy")
        st.pyplot(fig)


