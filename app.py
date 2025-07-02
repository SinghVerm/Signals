import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt

# === Load Data
@st.cache_data
def load_data():
    summary = pd.read_excel("Daily_Summary_with_Prioritized_Signal.xlsx")
    summary.columns = summary.columns.str.strip()
    df_30 = pd.read_csv("NSE_NIFTY, 30.csv", parse_dates=['time'])
    df_5 = pd.read_csv("NIFTY_5min_All_Sorted.csv", parse_dates=['time'])

    df_30['date'] = df_30['time'].dt.date
    df_5['date'] = df_5['time'].dt.date
    summary['Date'] = pd.to_datetime(summary['Date'], dayfirst=True)
    return summary, df_30, df_5

summary, df_30min, df_5min = load_data()

# === Start Year Filter
summary['Date'] = pd.to_datetime(summary['Date'], dayfirst=True)
date_years = sorted(summary['Date'].dropna().dt.year.astype(int).unique())
start_year = st.selectbox("Start Year", options=date_years[::-1], index=0)
summary = summary[summary['Date'].dt.year >= start_year]

# === Debug: Inspect data loading
st.write("Sample 5-min data:", df_5min.head())
st.write("Unique 5-min dates:", df_5min['date'].unique()[:5])
available_5min_dates = set(df_5min['date'].unique())

st.title("NIFTY Signal Analyzer")

# === UI Filters

# Year range filter
summary['Date'] = pd.to_datetime(summary['Date'])
date_years = sorted(summary['Date'].dropna().dt.year.astype(int).unique())
start_year = st.selectbox("Start Year", options=date_years[::-1], index=0)

# Filter summary from selected year onward
summary = summary[summary['Date'].dt.year >= start_year]
summary = summary[pd.to_datetime(summary['Date']).dt.year >= start_year]

# Filter summary by year
summary = summary[pd.to_datetime(summary['Date']).dt.year >= start_year]
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

# === Debug: Inspect filtered summary dates
st.write("Filtered dates:", filtered['Date'].unique()[:5])

# === Debug: Inspect filtered summary dates

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
    candle_numbers = st.multiselect("5-min Candle Numbers (starting from 2nd)", options=list(range(2, 10)), default=[2])

    valid_dates = []
    missing_dates = []

    for date in filtered['Date'].unique():
        date_obj = pd.to_datetime(date).date()
        if date_obj not in available_5min_dates:
            missing_dates.append(date)
            continue

        try:
            first_30 = df_30min[df_30min['date'] == date].iloc[0]
            high = first_30['high']
            low = first_30['low']

            day_df = df_5min[df_5min['date'] == date_obj].reset_index(drop=True)
            df_window = day_df.iloc[[i - 1 for i in candle_numbers if i - 1 < len(day_df)]]

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
                    last_close = df_5min[df_5min['date'] == date_obj].iloc[-1]['close']
                    move_value = round(last_close - breakout_close, 2)
                    breakout_moves[date] = move_value

        except:
            continue

    st.info(f"Out of {len(filtered)} matching days, {len(valid_dates)} have 5-min data and are used for confirmation.")
    if missing_dates:
        st.warning(f"{len(missing_dates)} days skipped due to missing 5-min data.")

    filtered = filtered[filtered['Date'].isin(valid_dates)]

# === 30-Min Confirmation (Optional)
st.markdown("### 30-Min Confirmation (Optional)")
use_30_confirmation = st.checkbox("Enable 30-min candle condition")

if use_30_confirmation:
    logic_30 = st.radio("30-Min Condition", [
        "Close Above First 30-min High",
        "Close Below First 30-min Low",
        "No Breakout (Neither Above Nor Below)",
        "Goes Above Close Below",
        "Goes Below Close Above"
    ])
    candle_numbers_30 = st.multiselect("30-min Candle Numbers (starting from 2nd)", options=list(range(2, 10)), default=[2])

    valid_dates_30 = []
    missing_30 = []

    for date in filtered['Date'].unique():
        df_day = df_30min[df_30min['date'] == pd.to_datetime(date).date()]

        if df_day.empty:
            missing_30.append(date)
            continue

        try:
            first_candle = df_day.iloc[0]
            high = first_candle['high']
            low = first_candle['low']

            df_window = df_day.reset_index(drop=True).iloc[[i - 1 for i in candle_numbers_30 if i - 1 < len(df_day)]]

            condition_met = False
            breakout_candle = None

            for _, row in df_window.iterrows():
                c_high = row['high']
                c_low = row['low']
                c_close = row['close']

                if logic_30 == "Close Above First 30-min High" and c_close > high:
                    condition_met = True; breakout_candle = row; break
                elif logic_30 == "Close Below First 30-min Low" and c_close < low:
                    condition_met = True; breakout_candle = row; break
                elif logic_30 == "No Breakout (Neither Above Nor Below)":
                    if (df_window['close'] <= high).all() and (df_window['close'] >= low).all():
                        condition_met = True; breakout_candle = df_window.iloc[0]; break
                elif logic_30 == "Goes Above Close Below" and c_high > high and c_close < high:
                    condition_met = True; breakout_candle = row; break
                elif logic_30 == "Goes Below Close Above" and c_low < low and c_close > low:
                    condition_met = True; breakout_candle = row; break

            if condition_met:
                valid_dates_30.append(date)
                if breakout_candle is not None:
                    breakout_close = breakout_candle['close']
                    last_close = df_day.iloc[-1]['close']
                    move_value = round(last_close - breakout_close, 2)
                    breakout_moves_30[date] = move_value

        except:
            continue

    st.info(f"Out of {len(filtered)} matching days, {len(valid_dates_30)} matched 30-min confirmation condition.")
    if missing_30:
        st.warning(f"{len(missing_30)} days skipped due to missing 30-min data.")

    filtered = filtered[filtered['Date'].isin(valid_dates_30)]

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

    if use_confirmation and breakout_moves:
        filtered['5_Move'] = filtered['Date'].map(breakout_moves)

    filtered_display = filtered.copy()
    filtered_display['Date'] = pd.to_datetime(filtered_display['Date'], dayfirst=True)
    filtered_display = filtered_display.sort_values(by="Date", ascending=False).reset_index(drop=True)
    filtered_display['Formatted_Date'] = filtered_display['Date'].dt.strftime("%d %b, %y")

    display_cols = ['Formatted_Date', 'Signal', 'Candles', 'Move.1', 'Move']
    if '5_Move' in filtered.columns:
        display_cols.append('5_Move')
    if 'Prev_Move' in filtered.columns:
        display_cols.append('Prev_Move')

    filtered_display = filtered_display.sort_values(by="Date", ascending=False).reset_index(drop=True)

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
