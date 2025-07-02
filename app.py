import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# === Load Data
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
available_5min_dates = set(df_5min['date'].unique())

st.title("NIFTY Signal Analyzer")

# === UI Filters
signal_list = ['Any'] + sorted(summary['Signal'].dropna().unique())
candle_list = ['Any'] + sorted(summary['Candles'].dropna().unique())

signal = st.selectbox("Select Signal", signal_list)
candle_type = st.selectbox("Candle Type", candle_list)

# === Prev_Move Filter
if 'Prev_Move' in summary.columns:
    label_mapping = {
        "Very Strong Long": "Very Strong Long (>= 1.00%)",
        "Moderate Long": "Moderate Long (0.40% to 1.00%)",
        "Sideways": "Sideways (-0.40% to +0.40%)",
        "Moderate Short": "Moderate Short (-0.40% to -1.00%)",
        "Very Strong Short": "Very Strong Short (<= -1.00%)"
    }
    raw_values = summary['Prev_Move'].dropna().unique()
    options = ['Any'] + [label_mapping[val] for val in raw_values if val in label_mapping]
    selected_label = st.selectbox("Previous Day View", options)

# === Filtering
filtered = summary.copy()
if signal != "Any":
    filtered = filtered[filtered['Signal'] == signal]
if candle_type != "Any":
    filtered = filtered[filtered['Candles'] == candle_type]
if 'Prev_Move' in summary.columns and selected_label != "Any":
    reverse_mapping = {v: k for k, v in label_mapping.items()}
    selected_base = reverse_mapping[selected_label]
    filtered = filtered[filtered['Prev_Move'] == selected_base]

# === Initialize Flags
use_confirmation = False
use_30_confirmation = False
breakout_moves = {}
breakout_moves_30 = {}

# === 5-Min Confirmation (Optional)
st.markdown("### 5-Min Confirmation (Optional)")
use_confirmation = st.checkbox("Enable 5-min candle condition")

if use_confirmation:
    logic = st.radio("Condition", [
        "Close Above First 30-min High",
        "Close Below First 30-min Low",
        "No Breakout (Neither Above Nor Below)"
    ])
    valid_dates = []
    missing_dates = []

    for ts in filtered['Date'].unique():
        date = ts.date()
        if date not in available_5min_dates:
            missing_dates.append(date)
            continue

        try:
            first_30 = df_30min[df_30min['date'] == date].iloc[0]
            high = first_30['high']
            low = first_30['low']

            day_df = df_5min[df_5min['date'] == date].sort_values("time").reset_index(drop=True)
            df_window = day_df.iloc[6:12]

            condition_met = False
            breakout_candle = None

            if logic == "Close Above First 30-min High":
                breakout_rows = df_window[df_window['close'] > high]
                if not breakout_rows.empty:
                    condition_met = True
                    breakout_candle = breakout_rows.iloc[0]
            elif logic == "Close Below First 30-min Low":
                breakout_rows = df_window[df_window['close'] < low]
                if not breakout_rows.empty:
                    condition_met = True
                    breakout_candle = breakout_rows.iloc[0]
            elif logic == "No Breakout (Neither Above Nor Below)":
                not_above = (df_window['close'] <= high).all()
                not_below = (df_window['close'] >= low).all()
                condition_met = not_above and not_below
                breakout_candle = df_window.iloc[0] if condition_met else None

            if condition_met:
                valid_dates.append(date)
                if breakout_candle is not None:
                    breakout_close = breakout_candle['close']
                    last_close = df_5min[df_5min['date'] == date].iloc[-1]['close']
                    move_value = round(last_close - breakout_close, 2)
                    breakout_moves[date] = move_value

        except:
            continue

    st.info(f"Out of {len(filtered)} matching days, {len(valid_dates)} have 5-min data and are used for confirmation.")
    if missing_dates:
        st.warning(f"{len(missing_dates)} days skipped due to missing 5-min data.")

    filtered = filtered[filtered['date'].isin(valid_dates)]
    if breakout_moves:
        filtered["5_Move"] = filtered["date"].map(breakout_moves)

# === 30-Min Flag Filter
st.markdown("### 30-Min Flag Filter (Optional)")
enable_30_flag = st.checkbox("Enable 30-min flag filter")
if enable_30_flag:
    level = st.selectbox("Which level?", ["Any", "High", "Mid", "Yesterday Low"])
    result = st.selectbox("Result", ["Any", "Touch & Close Above", "Touch & Close Below", "No Touch"])
    if level != "Any" and result != "Any":
        matched_dates = df_30min[df_30min[level] == result]["date"].unique()
        filtered = filtered[filtered["date"].isin(matched_dates)]

# === Results Summary
st.markdown(f"### Filtered Results: {len(filtered)} Days Matched")

if len(filtered) > 0:
    move_counts = filtered['Move.1'].value_counts()
    long_count = move_counts.get("Long", 0)
    short_count = move_counts.get("Short", 0)
    total = long_count + short_count
    long_pct = (long_count / total * 100) if total else 0
    short_pct = (short_count / total * 100) if total else 0

    st.write(f"Long: {long_count} ({long_pct:.2f}%)")
    st.write(f"Short: {short_count} ({short_pct:.2f}%)")

    if 'Move' in filtered.columns:
        st.markdown("### Move in Points")
        st.write(f"Average Move (abs): {filtered['Move'].abs().mean():.2f} pts")
        st.write(f"Max Move: {filtered['Move'].max():.2f} pts")
        st.write(f"Min Move: {filtered['Move'].min():.2f} pts")

    filtered_display = filtered.copy()
    filtered_display['Date'] = pd.to_datetime(filtered_display['Date'], dayfirst=True)
    filtered_display = filtered_display.sort_values(by="Date", ascending=False).reset_index(drop=True)
    filtered_display['Formatted_Date'] = filtered_display['Date'].dt.strftime("%d %b, %y")

    display_cols = ['Formatted_Date', 'Signal', 'Candles', 'Move.1', 'Move']
    for col in ['High', 'Mid', 'Yesterday Low']:
        if col in filtered_display.columns:
            display_cols.append(col)
    if '5_Move' in filtered_display.columns:
        display_cols.append('5_Move')
    if 'Prev_Move' in filtered_display.columns:
        display_cols.append('Prev_Move')

    st.dataframe(filtered_display[display_cols].rename(columns={'Formatted_Date': 'Date'}))

    st.markdown("### Periodic Accuracy Breakdown")
    period_option = st.selectbox("Group By", ["Month", "Quarter", "Year"], index=2)

    df = filtered.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    if period_option == "Month":
        df['Period'] = df['Date'].dt.to_period("M").astype(str)
    elif period_option == "Quarter":
        df['Period'] = df['Date'].dt.to_period("Q").astype(str)
    else:
        df['Period'] = df['Date'].dt.year.astype(str)

    pivot = df.groupby('Period')['Move.1'].value_counts().unstack(fill_value=0)
    pivot['Total'] = pivot.sum(axis=1)
    pivot['Long %'] = round((pivot.get('Long', 0) / pivot['Total']) * 100, 2)
    pivot['Short %'] = round((pivot.get('Short', 0) / pivot['Total']) * 100, 2)

    st.dataframe(pivot[['Long', 'Short', 'Total', 'Long %', 'Short %']].sort_index())

    st.markdown("### Accuracy Chart")
    fig, ax = plt.subplots()
    pivot[['Long %', 'Short %']].plot(kind='bar', ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Accuracy (%)")
    plt.title(f"{period_option}ly Accuracy")
    st.pyplot(fig)

else:
    st.warning("No matching data found.")
