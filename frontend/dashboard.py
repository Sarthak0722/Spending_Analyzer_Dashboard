import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt

# --- Recharge validity mapping ---
RECHARGE_VALIDITY = {
    149: 20, 199: 28, 239: 28, 299: 28, 349: 28, 399: 28,
    179: 28, 269: 28,
    187: 28, 247: 28, 319: 28
}

# --- Page config ---
st.set_page_config(page_title="Spending Anomaly Dashboard", layout="wide")
st.title("📊 Spending Anomaly Dashboard")

# --- User Guide ---
with st.expander("📘 Click here to read the User Guide"):
    st.markdown("""
    ### 👋 Welcome to the Spending Analyzer Dashboard!

    This tool helps you detect financial anomalies and understand your spending.

    #### 📤 Uploading
    - Upload your transaction CSV file (exported from bank/UPI app or our synthetic generator).

    #### 🔍 Features
    - **🔁 Duplicate Transactions:** Detects repeated payments within 3 minutes.
    - **💥 Spending Spikes:** Flags unusually large transactions.
    - **🌍 Out-of-City Transactions:** Catches spending outside your usual location.
    - **📅 Active Recharges:** Shows valid recharge plans and their due dates.
    - **📊 Insights Dashboard:** Visualize your spending patterns and habits.

    #### ⚠️ Format Requirements
    - CSV must include: `date`, `time`, `amount`, `merchant`, `txn_type`, `payment_mode`, `city`, `category`.

    #### 📌 Need Help?
    Contact the developer or check the README file.
    """)

# --- Upload CSV ---
uploaded_file = st.file_uploader("📂 Upload your transaction CSV", type=['csv'])

# --- Helper functions ---
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

def detect_spikes(df):
    median_amt = df['amount'].median()
    return df[df['amount'] > 10 * median_amt]

def detect_out_of_city(df, base_city="Pune"):
    return df[df['city'] != base_city]

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

def show_visualizations(df):
    st.subheader("📊 Transaction Insights")

    # Total Spending per Category
    cat_chart = px.pie(df, names='category', values='amount', title='Category-wise Spending')
    st.plotly_chart(cat_chart, use_container_width=True)

    # Top Merchants by Spend
    top_merchants = df.groupby('merchant')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
    merchant_chart = px.bar(top_merchants, x='merchant', y='amount', title='Top 10 Merchants by Spend')
    st.plotly_chart(merchant_chart, use_container_width=True)

    # Monthly Spending Trend
    df['month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
    monthly = df.groupby('month')['amount'].sum().reset_index()
    monthly_chart = px.line(monthly, x='month', y='amount', title='Monthly Spending Trend')
    st.plotly_chart(monthly_chart, use_container_width=True)

    # Payment Mode Usage
    paymode_chart = px.pie(df, names='payment_mode', title='Payment Mode Distribution')
    st.plotly_chart(paymode_chart, use_container_width=True)

    # City-wise Spending
    city_spending = df.groupby('city')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
    city_chart = px.bar(city_spending, x='city', y='amount', title='Top Cities by Spend')
    st.plotly_chart(city_chart, use_container_width=True)

    # Weekly Spending Heatmap
    df['day'] = pd.to_datetime(df['date']).dt.day_name()
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    heatmap_data = df.groupby(['day', 'hour'])['amount'].sum().unstack().fillna(0)
    st.markdown("#### Weekly Spending Heatmap")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.heatmap(heatmap_data, cmap="YlGnBu", ax=ax)
    st.pyplot(fig)

    # Transaction Amount vs Count
    st.markdown("#### Transaction Amount vs Frequency")
    txn_counts = df.groupby('amount').size().reset_index(name='count')
    scatter = px.scatter(txn_counts, x='amount', y='count', title='Transaction Amount vs Frequency')
    st.plotly_chart(scatter, use_container_width=True)

# --- Main logic ---
if uploaded_file:
    df = pd.read_csv(uploaded_file)

    try:
        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    except Exception as e:
        st.error("⚠️ Failed to parse date/time. Please ensure correct format in `date` and `time` columns.")
        st.stop()

    # Run anomaly detections
    duplicates = detect_duplicates(df)
    spikes = detect_spikes(df)
    out_city = detect_out_of_city(df)
    current_recharges = detect_all_current_recharges(df)

    # Show visuals
    show_visualizations(df)

    # Show tables
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
