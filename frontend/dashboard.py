import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import requests

# --- Setup ---
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

RECHARGE_VALIDITY = {
    149: 20, 199: 28, 239: 28, 299: 28, 349: 28, 399: 28,
    179: 28, 269: 28, 187: 28, 247: 28, 319: 28
}

st.set_page_config(page_title="Spending Anomaly Dashboard", layout="wide")
st.title("📊 Spending Anomaly Dashboard")

uploaded_file = st.file_uploader("📂 Upload your transaction CSV", type=['csv'])

# === Utility Functions ===

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
                days_remaining = (end_date - datetime.now()).days
                active_recharges.append({
                    'Merchant': merchant,
                    'Amount': amount,
                    'Start Date': start_date.strftime('%Y-%m-%d'),
                    'Due Date': end_date.strftime('%Y-%m-%d'),
                    'Days Remaining': days_remaining,
                    'Validity (days)': validity_days
                })
                seen.add((merchant, amount))
    return pd.DataFrame(active_recharges)

def header_with_info_inline(title, explanation):
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <span style="font-weight: 600; font-size: 18px;">{title}</span>
            <span title="{explanation}" style="font-size: 14px; cursor: help; color: #555;">ℹ️</span>
        </div>
        """, unsafe_allow_html=True
    )

# === Main Flow ===

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])

    duplicates = detect_duplicates(df)
    spikes = detect_spikes(df)
    out_city = detect_out_of_city(df)
    current_recharges = detect_all_current_recharges(df)

    df['month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
    df['day'] = pd.to_datetime(df['date']).dt.day_name()
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    txn_counts = df.groupby('amount').size().reset_index(name='count')
    top_merchants = df.groupby('merchant')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
    top_cities = df.groupby('city')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
    monthly = df.groupby('month')['amount'].sum().reset_index()
    heatmap_data = df.groupby(['day', 'hour'])['amount'].sum().unstack().fillna(0)

    top_cat = df.groupby('category')['amount'].sum().idxmax()
    cat_amt = df.groupby('category')['amount'].sum().max()
    total_amt = df['amount'].sum()
    top_mode = df['payment_mode'].value_counts().idxmax()
    top_merchant = top_merchants.iloc[0]['merchant']
    merchant_amt = int(top_merchants.iloc[0]['amount'])
    top_city = top_cities.iloc[0]['city']
    city_amt = int(top_cities.iloc[0]['amount'])
    highest_month = monthly.loc[monthly['amount'].idxmax()]
    peak_day = heatmap_data.sum(axis=1).idxmax()
    peak_hour = heatmap_data.sum(axis=0).idxmax()
    common_amt = txn_counts.loc[txn_counts['count'].idxmax(), 'amount']

    insights = [
        ("💼 Top Category", f"{top_cat} ({(cat_amt/total_amt)*100:.1f}%)"),
        ("💳 Most Used Mode", top_mode),
        ("🏪 Top Merchant", f"{top_merchant} (₹{merchant_amt})"),
        ("🌆 Top City", f"{top_city} (₹{city_amt})"),
        ("📅 Peak Month", f"{highest_month['month']} (₹{int(highest_month['amount'])})"),
        ("🕒 Peak Time", f"{peak_day}s at {peak_hour}:00"),
        ("💸 Common Amount", f"₹{common_amt}"),
    ]

    tab0, tab1, tab2, tab3, tab4 = st.tabs([
        "🧠 Summary", "📊 Visualizations", "🚨 Anomalies", "📅 Active Plans", "💬 Chatbot"
    ])

    with tab0:
        # st.header("🧠 Summary Insights")
        card_chunks = [insights[i:i+3] for i in range(0, len(insights), 3)]
        for row in card_chunks:
            cols = st.columns(len(row))
            for col, (label, value) in zip(cols, row):
                with col:
                    st.markdown(f"""
                        <div style="
                            background-color: #f9f9f9;
                            padding: 14px 18px;
                            border-radius: 12px;
                            text-align: center;
                            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
                            height: 100px;
                            display: flex;
                            flex-direction: column;
                            justify: center;
                            align-items: center;
                            margin: 6px 6px 12px 6px;
                        ">
                            <div style="font-size: 16px; font-weight: 700; color: #222;">{label}</div>
                            <div style="font-size: 18px; font-weight: 600; color: #111;">{value}</div>
                        </div>
                    """, unsafe_allow_html=True)

    with tab1:
        # st.header("📊 Spending Visualizations")
        col1, col2 = st.columns([3, 1])
        with col2:
            selection = st.radio("Choose Visualization", [
                "📂 Category", "💳 Payment Modes", "🏪 Top Merchants",
                "🌆 Top Cities", "📅 Monthly Trends", "📈 Heatmap & Frequency"
            ])
        
        with col1:
            if selection == "📂 Category":
                header_with_info_inline("Category-wise Spending", "Shows your spending distribution across categories.")
                st.plotly_chart(px.pie(df, names='category', values='amount'), use_container_width=True)
            elif selection == "💳 Payment Modes":
                header_with_info_inline("Payment Mode Usage", "Shows how often you use UPI, credit card, etc.")
                st.plotly_chart(px.pie(df, names='payment_mode'), use_container_width=True)
            elif selection == "🏪 Top Merchants":
                header_with_info_inline("Top 10 Merchants by Spend", "Merchants where you spend the most money.")
                st.plotly_chart(px.bar(top_merchants, x='merchant', y='amount'), use_container_width=True)
            elif selection == "🌆 Top Cities":
                header_with_info_inline("Top Cities by Spending", "Cities where your transactions mostly happen.")
                st.plotly_chart(px.bar(top_cities, x='city', y='amount'), use_container_width=True)
            elif selection == "📅 Monthly Trends":
                header_with_info_inline("Monthly Spending Trend", "Line chart showing your total monthly spend.")
                st.plotly_chart(px.line(monthly, x='month', y='amount'), use_container_width=True)
            elif selection == "📈 Heatmap & Frequency":
                header_with_info_inline("Weekly Spending Heatmap", "What days/hours you spend the most money.")
                fig, ax = plt.subplots(figsize=(10, 4))
                sns.heatmap(heatmap_data, cmap="YlGnBu", ax=ax)
                st.pyplot(fig)

                header_with_info_inline("Transaction Amount vs Frequency", "Scatter showing frequently used transaction amounts.")
                st.plotly_chart(px.scatter(txn_counts, x='amount', y='count'), use_container_width=True)

    with tab2:
        # st.header("🚨 Detected Anomalies")
        with st.expander("🔁 Double Payments"):
            st.markdown("**Why this matters:** These could be accidental repeat payments or system errors.")
            st.dataframe(duplicates)

        with st.expander("💥 Spending Spikes"):
            st.markdown("**Why this matters:** Unusually large amounts could indicate emergencies or fraud.")
            st.dataframe(spikes)

        with st.expander("🌍 Out-of-City Transactions"):
            st.markdown("**Why this matters:** Transactions outside your usual city may signal travel or unauthorized use.")
            st.dataframe(out_city)

    with tab3:
        # st.header("📅 Active Recharges")
        if current_recharges.empty:
            st.warning("⚠️ No active recharges.")
        else:
            st.dataframe(current_recharges)

    with tab4:
        st.header("💬 Chat with AI About Your Spending")
        user_question = st.text_input("Ask any question:")
        if user_question and OPENROUTER_API_KEY:
            with st.spinner("🤖 Thinking..."):
                try:
                    messages = [
                        {"role": "system", "content": "You are a helpful financial assistant. Use the user's insights to answer clearly."},
                        {"role": "user", "content": f"Here are my insights:\n{insights}\n\nQuestion: {user_question}"}
                    ]
                    headers = {
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "model": "deepseek/deepseek-r1:free",
                        "messages": messages
                    }
                    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
                    if response.status_code == 200:
                        reply = response.json()['choices'][0]['message']['content']
                        st.success(reply)
                    else:
                        st.error("OpenRouter API error: " + response.text)
                except Exception as e:
                    st.error(f"Chatbot error: {e}")
        elif user_question:
            st.warning("Please set your OPENROUTER_API_KEY in .env to enable chatbot.")
else:
    st.info("⬆️ Please upload a transaction CSV to begin.")
