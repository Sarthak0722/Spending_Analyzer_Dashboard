import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- Recharge validity mapping ---
RECHARGE_VALIDITY = {
    149: 20, 199: 28, 239: 28, 299: 28, 349: 28, 399: 28,
    179: 28, 269: 28,
    187: 28, 247: 28, 319: 28
}

st.set_page_config(page_title="Spending Anomaly Dashboard", layout="wide")
st.title("📊 Spending Anomaly Dashboard")

uploaded_file = st.file_uploader("Upload your transaction CSV", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])

    # Detect Duplicate Payments
    def detect_duplicates(df):
        df_sorted = df.sort_values('timestamp').reset_index()
        duplicate_indices = set()
        for i in range(len(df_sorted)):
            current = df_sorted.iloc[i]
            for j in range(i + 1, len(df_sorted)):
                candidate = df_sorted.iloc[j]
                time_diff = (candidate['timestamp'] - current['timestamp']).total_seconds() / 60
                if time_diff > 3:
                    break
                if (
                    current['amount'] == candidate['amount'] and
                    current['merchant'] == candidate['merchant'] and
                    current['txn_type'] == candidate['txn_type'] and
                    current['payment_mode'] == candidate['payment_mode'] and
                    current['city'] == candidate['city']
                ):
                    duplicate_indices.add(current['index'])
                    duplicate_indices.add(candidate['index'])
        return df.loc[list(duplicate_indices)].sort_values('timestamp')

    # Detect Spikes
    def detect_spikes(df):
        median_amt = df['amount'].median()
        return df[df['amount'] > 10 * median_amt]

    # Detect Out-of-City
    def detect_out_of_city(df, base_city="Pune"):
        return df[df['city'] != base_city]

    # Detect All Active Recharges
    def detect_all_current_recharges(df):
        recharge_df = df[df['category'] == 'Recharge'].sort_values('timestamp', ascending=False)
        active_recharges = []

        seen = set()
        for _, row in recharge_df.iterrows():
            amount = row['amount']
            merchant = row['merchant']
            if (merchant, amount) in seen:
                continue
            if amount in RECHARGE_VALIDITY:
                start_date = row['timestamp']
                validity_days = RECHARGE_VALIDITY[amount]
                end_date = start_date + timedelta(days=validity_days)
                if end_date > datetime.now():
                    active_recharges.append({
                        'Merchant': merchant,
                        'Amount': amount,
                        'Start Date': start_date.strftime('%Y-%m-%d'),
                        'Due Date': end_date.strftime('%Y-%m-%d'),
                        'Validity (days)': validity_days
                    })
                    seen.add((merchant, amount))
        return pd.DataFrame(active_recharges)

    # Run all detections
    duplicates = detect_duplicates(df)
    spikes = detect_spikes(df)
    out_city = detect_out_of_city(df)
    current_recharges = detect_all_current_recharges(df)

    # Display Results
    st.subheader("🔁 Duplicate Transactions (within 3 minutes)")
    st.dataframe(duplicates[['timestamp', 'merchant', 'amount', 'payment_mode', 'city']])

    st.subheader("💥 Spike Transactions (10× median)")
    st.dataframe(spikes[['timestamp', 'merchant', 'amount', 'payment_mode', 'city']])

    st.subheader("🌍 Out-of-City Transactions")
    st.dataframe(out_city[['timestamp', 'merchant', 'amount', 'payment_mode', 'city']])

    st.subheader("📅 Currently Active Recharges")
    if current_recharges.empty:
        st.warning("⚠️ No currently valid recharges found.")
    else:
        st.dataframe(current_recharges)

else:
    st.info("⬆️ Please upload a transaction CSV to begin.")
