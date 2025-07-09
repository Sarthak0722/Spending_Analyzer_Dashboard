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

with st.expander("📘 Click here to read the User Guide"):
    st.markdown("""
    ### 👋 Welcome to the Spending Analyzer Dashboard!

    Upload your transaction CSV to:
    - Detect financial anomalies
    - Visualize trends
    - Ask questions via Chatbot about your own data
    """)

uploaded_file = st.file_uploader("📂 Upload your transaction CSV", type=['csv'])

# === All Functions ===

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

# === Helper: Inline Header with Tooltip ===

def header_with_info_inline(title, explanation):
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <span style="font-weight: 600; font-size: 18px;">{title}</span>
            <span title="{explanation}" style="
                font-size: 14px;
                cursor: help;
                color: #555;
            ">ℹ️</span>
        </div>
        """,
        unsafe_allow_html=True
    )



# === Main Flow ===

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])

    duplicates = detect_duplicates(df)
    spikes = detect_spikes(df)
    out_city = detect_out_of_city(df)
    current_recharges = detect_all_current_recharges(df)

    insights = []

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Visualizations", 
        "🚨 Anomalies", 
        "📅 Recharges", 
        "💬 Chatbot"
    ])

    with tab1:
        st.header("📊 Spending Visualizations")

        col1, col2 = st.columns(2)
        with col1:
            header_with_info_inline("Category-wise Spending", "Shows your spending distribution across categories.")
            cat_chart = px.pie(df, names='category', values='amount')
            st.plotly_chart(cat_chart, use_container_width=True)

        with col2:
            header_with_info_inline("Payment Mode Usage", "Shows how often you use UPI, credit card, etc.")
            mode_chart = px.pie(df, names='payment_mode')
            st.plotly_chart(mode_chart, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            header_with_info_inline("Top 10 Merchants by Spend", "Merchants where you spend the most money.")
            top_merchants = df.groupby('merchant')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
            merch_chart = px.bar(top_merchants, x='merchant', y='amount')
            st.plotly_chart(merch_chart, use_container_width=True)

        with col4:
            header_with_info_inline("Top Cities by Spending", "Cities where your transactions mostly happen.")
            top_cities = df.groupby('city')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
            city_chart = px.bar(top_cities, x='city', y='amount')
            st.plotly_chart(city_chart, use_container_width=True)

        df['month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
        monthly = df.groupby('month')['amount'].sum().reset_index()
        header_with_info_inline("Monthly Spending Trend", "Line chart showing your total monthly spend.")
        month_chart = px.line(monthly, x='month', y='amount')
        st.plotly_chart(month_chart, use_container_width=True)

        df['day'] = pd.to_datetime(df['date']).dt.day_name()
        df['hour'] = pd.to_datetime(df['time']).dt.hour
        heatmap_data = df.groupby(['day', 'hour'])['amount'].sum().unstack().fillna(0)
        header_with_info_inline("Weekly Spending Heatmap", "What days/hours you spend the most money.")
        fig, ax = plt.subplots(figsize=(10, 4))
        sns.heatmap(heatmap_data, cmap="YlGnBu", ax=ax)
        st.pyplot(fig)

        peak_day = heatmap_data.sum(axis=1).idxmax()
        peak_hour = heatmap_data.sum(axis=0).idxmax()
        st.info(f"🕒 You spend most often on **{peak_day}s** around **{peak_hour}:00 hours**.")

        txn_counts = df.groupby('amount').size().reset_index(name='count')
        header_with_info_inline("Transaction Amount vs Frequency", "Scatter showing frequently used transaction amounts.")
        scatter = px.scatter(txn_counts, x='amount', y='count')
        st.plotly_chart(scatter, use_container_width=True)

        common_amt = txn_counts.loc[txn_counts['count'].idxmax(), 'amount']
        st.info(f"💸 Your most frequent transaction amount is **₹{common_amt}**.")

        top_cat = df.groupby('category')['amount'].sum().idxmax()
        cat_amt = df.groupby('category')['amount'].sum().max()
        total_amt = df['amount'].sum()
        insights.append(f"Top category: {top_cat} ({(cat_amt/total_amt)*100:.1f}% of spend)")
        top_mode = df['payment_mode'].value_counts().idxmax()
        insights.append(f"Most used payment mode: {top_mode}")
        insights.append(f"Top merchant: {top_merchants.iloc[0]['merchant']} - ₹{int(top_merchants.iloc[0]['amount'])}")
        insights.append(f"Top spending city: {top_cities.iloc[0]['city']} - ₹{int(top_cities.iloc[0]['amount'])}")
        highest_month = monthly.loc[monthly['amount'].idxmax()]
        insights.append(f"Highest spending month: {highest_month['month']} - ₹{int(highest_month['amount'])}")

        st.markdown("### 🧠 Key Summary Insights:")
        for ins in insights:
            st.markdown(f"- {ins}")

    with tab2:
        st.header("🚨 Detected Anomalies")

        with st.expander("🔁 Duplicate Transactions"):
            st.markdown("**Why this matters:** Duplicate transactions may be accidental double payments or bank/server errors.")
            st.dataframe(duplicates)

        with st.expander("💥 Spending Spikes"):
            st.markdown("**Why this matters:** Sudden high-value transactions may indicate unusual behavior or financial stress.")
            st.dataframe(spikes)

        with st.expander("🌍 Out-of-City Transactions"):
            st.markdown("**Why this matters:** Spending outside your usual city might indicate travel, fraud, or family spending.")
            st.dataframe(out_city)

    with tab3:
        st.header("📅 Active Recharges")
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
                        {
                            "role": "system",
                            "content": "You are a helpful financial assistant. Use the user's insights to answer clearly."
                        },
                        {
                            "role": "user",
                            "content": f"Here are my insights:\n{insights}\n\nQuestion: {user_question}"
                        }
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
