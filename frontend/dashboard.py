import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import requests
from sqlalchemy import create_engine
import sqlite3
import time as time_module
import subprocess
from streamlit_autorefresh import st_autorefresh

# --- Setup ---
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

RECHARGE_VALIDITY = {
    149: 20, 199: 28, 239: 28, 299: 28, 349: 28, 399: 28,
    179: 28, 269: 28, 187: 28, 247: 28, 319: 28
}

st.set_page_config(page_title="Spending Anomaly Dashboard", layout="wide")
st.title("📊 Spending Anomaly Dashboard")

# --- Data Source Selection ---
data_source = st.radio(
    "Select data source:",
    ["Upload CSV", "Connect to UPI (dummy simulation)"],
    horizontal=True
)

uploaded_file = None
sim_db_path = "../simulated_transactions.db" if not os.path.exists("simulated_transactions.db") else "simulated_transactions.db"

if data_source == "Upload CSV":
    uploaded_file = st.file_uploader("📂 Upload your transaction CSV", type=['csv'])

REQUIRED_COLUMNS = {'date', 'time', 'amount', 'merchant', 'txn_type', 'category', 'city'}

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
if 'upi_sim_initialized' not in st.session_state:
    st.session_state['upi_sim_initialized'] = False

if data_source == "Connect to UPI (dummy simulation)" and not st.session_state['upi_sim_initialized']:
    # Clean the database (delete all transactions)
    try:
        conn = sqlite3.connect(sim_db_path)
        c = conn.cursor()
        c.execute("DELETE FROM transactions")
        conn.commit()
        conn.close()
    except Exception as e:
        st.warning(f"Could not clean the database: {e}")

    # Start the simulator in the background if not already running
    import psutil
    import sys
    simulator_running = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'upi_simulator.py' in ' '.join(proc.info['cmdline']):
                simulator_running = True
                break
        except Exception:
            continue
    if not simulator_running:
        try:
            subprocess.Popen([sys.executable, os.path.abspath(os.path.join(os.path.dirname(__file__), '../upi_simulator.py'))])
            st.success("Started UPI simulator in the background. Your transactions will be automatically fetched from your upi app. Please refesh to see latest transactions. For dummy purpose this will currently generate 1 transaction per 10 sec.")
        except Exception as e:
            st.error(f"Failed to start UPI simulator: {e}")
    st.session_state['upi_sim_initialized'] = True

if data_source != "Connect to UPI (dummy simulation)":
    st.session_state['upi_sim_initialized'] = False

refresh = False
if data_source == "Connect to UPI (dummy simulation)":
    refresh = st.button("🔄 Refresh transactions", help="Click to manually refresh the dashboard with the latest transactions.")
    if refresh:
        st.rerun()

if (data_source == "Upload CSV" and uploaded_file) or (data_source == "Connect to UPI (dummy simulation)"):
    try:
        if data_source == "Upload CSV":
            df = pd.read_csv(uploaded_file)
        else:
            # --- Fetch from SQLite simulation ---
            engine = create_engine(f'sqlite:///{sim_db_path}')
            df = pd.read_sql("SELECT * FROM transactions", engine)

        # === Check Format ===
        uploaded_columns = set(df.columns)
        missing_cols = REQUIRED_COLUMNS - uploaded_columns
        if missing_cols:
            st.warning(f"Waiting for transactions... (Missing columns: {', '.join(missing_cols)})")
            for col in REQUIRED_COLUMNS:
                if col not in df.columns:
                    df[col] = []
        else:
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            df['month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
            df['day'] = pd.to_datetime(df['date']).dt.day_name()
            df['hour'] = pd.to_datetime(df['time']).dt.hour

        # Run all detectors (handle empty df gracefully)
        duplicates = detect_duplicates(df) if not df.empty else pd.DataFrame()
        spikes = detect_spikes(df) if not df.empty else pd.DataFrame()
        out_city = detect_out_of_city(df) if not df.empty else pd.DataFrame()
        current_recharges = detect_all_current_recharges(df) if not df.empty else pd.DataFrame()

        # Preprocessing for visualizations (handle empty df)
        txn_counts = df.groupby('amount').size().reset_index(name='count') if not df.empty else pd.DataFrame()
        top_merchants = df.groupby('merchant')['amount'].sum().sort_values(ascending=False).head(10).reset_index() if not df.empty else pd.DataFrame()
        top_cities = df.groupby('city')['amount'].sum().sort_values(ascending=False).head(10).reset_index() if not df.empty else pd.DataFrame()
        monthly = df.groupby('month')['amount'].sum().reset_index() if not df.empty else pd.DataFrame()
        heatmap_data = df.groupby(['day', 'hour'])['amount'].sum().unstack().fillna(0) if not df.empty else pd.DataFrame()
        daily = df.groupby('date')['amount'].sum().reset_index() if not df.empty else pd.DataFrame()
        hourly = df.groupby('hour')['amount'].sum().reset_index() if not df.empty else pd.DataFrame()
        weekly_cat = df.groupby(['day', 'category'])['amount'].sum().reset_index() if not df.empty else pd.DataFrame()

        # Extracting Insights (handle empty df)
        if not df.empty:
            top_cat = df.groupby('category')['amount'].sum().idxmax()
            cat_amt = df.groupby('category')['amount'].sum().max()
            total_amt = df['amount'].sum()
            top_merchant = top_merchants.iloc[0]['merchant'] if not top_merchants.empty else "-"
            merchant_amt = int(top_merchants.iloc[0]['amount']) if not top_merchants.empty else 0
            top_city = top_cities.iloc[0]['city'] if not top_cities.empty else "-"
            city_amt = int(top_cities.iloc[0]['amount']) if not top_cities.empty else 0
            highest_month = monthly.loc[monthly['amount'].idxmax()] if not monthly.empty else {"month": "-", "amount": 0}
            peak_day = heatmap_data.sum(axis=1).idxmax() if not heatmap_data.empty else "-"
            peak_hour = heatmap_data.sum(axis=0).idxmax() if not heatmap_data.empty else "-"
            common_amt = txn_counts.loc[txn_counts['count'].idxmax(), 'amount'] if not txn_counts.empty else "-"
            insights = [
                ("💼 Top Category", f"{top_cat} ({(cat_amt/total_amt)*100:.1f}%)" if total_amt else "-"),
                ("🏪 Top Merchant", f"{top_merchant} (₹{merchant_amt})"),
                ("🌆 Top City", f"{top_city} (₹{city_amt})"),
                ("📅 Peak Month", f"{highest_month['month']} (₹{int(highest_month['amount'])})" if not monthly.empty else "-"),
                ("🕒 Peak Time", f"{peak_day}s at {peak_hour}:00"),
                ("💸 Common Amount", f"₹{common_amt}"),
            ]
        else:
            insights = [
                ("💼 Top Category", "-"),
                ("🏪 Top Merchant", "-"),
                ("🌆 Top City", "-"),
                ("📅 Peak Month", "-"),
                ("🕒 Peak Time", "-"),
                ("💸 Common Amount", "-"),
            ]

        # Tabs UI (always show tabs)
        tab0, tab1, tab2, tab3, tab4 = st.tabs([
            "🧠 Summary", "📊 Visualizations", "🚨 Anomalies", "📅 Active Plans", "💬 Chatbot"
        ])

        with tab0:
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
            if df.empty:
                st.info("No transactions yet. Visualizations will appear as soon as transactions are generated.")
            else:
                # --- Date Range Filter ---
                min_date = df['timestamp'].dt.date.min()
                max_date = df['timestamp'].dt.date.max()
                date_range = st.date_input(
                    "Select date range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key="date_range_filter"
                )
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start_date, end_date = date_range
                else:
                    start_date, end_date = min_date, max_date
                filtered_df = df[(df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)]

                col1, col2 = st.columns([3, 1])
                with col2:
                    selection = st.radio("Choose Visualization", [
                        "📂 Category", "🏪 Top Merchants",
                        "🌆 Top Cities", "📅 Monthly Trends", "📈 Heatmap","📉 Daily Trends",
                        "🕒 Hourly Spend", "🗓️ Weekly Category"
                    ])

                with col1:
                    if selection == "📂 Category":
                        header_with_info_inline("Category-wise Spending", "Shows your spending distribution across categories.")
                        st.plotly_chart(px.pie(filtered_df, names='category', values='amount'), use_container_width=True)
                    elif selection == "🏪 Top Merchants":
                        header_with_info_inline("Top 10 Merchants by Spend", "Merchants where you spend the most money.")
                        top_merchants_f = filtered_df.groupby('merchant')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
                        st.plotly_chart(px.bar(top_merchants_f, x='merchant', y='amount'), use_container_width=True)
                    elif selection == "🌆 Top Cities":
                        header_with_info_inline("Top Cities by Spending", "Cities where your transactions mostly happen.")
                        top_cities_f = filtered_df.groupby('city')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
                        st.plotly_chart(px.bar(top_cities_f, x='city', y='amount'), use_container_width=True)
                    elif selection == "📅 Monthly Trends":
                        header_with_info_inline("Monthly Spending Trend", "Line chart showing your total monthly spend.")
                        monthly_f = filtered_df.groupby('month')['amount'].sum().reset_index()
                        st.plotly_chart(px.line(monthly_f, x='month', y='amount'), use_container_width=True)
                    elif selection == "📈 Heatmap":
                        # Heatmap Visualization and Auto Explanation
                        header_with_info_inline("Weekly Spending Heatmap", "Shows your spending intensity by weekday and hour.")
                        heatmap_data_f = filtered_df.groupby(['day', 'hour'])['amount'].sum().unstack().fillna(0)
                        fig, ax = plt.subplots(figsize=(10, 4))
                        sns.heatmap(heatmap_data_f, cmap="YlGnBu", ax=ax)
                        st.pyplot(fig)

                        # Generate insights dynamically
                        if not heatmap_data_f.empty:
                            peak_day_heat = heatmap_data_f.sum(axis=1).idxmax()
                            peak_hour_heat = heatmap_data_f.sum(axis=0).idxmax()
                            heat_amt = int(heatmap_data_f.loc[peak_day_heat, peak_hour_heat])
                            st.markdown(f"""
                            <div style="margin-bottom: 16px; font-size: 15px; color: #f9f9f9;">
                            📌 Based on the heatmap, your highest spending typically occurs on <b>{peak_day_heat}</b> around <b>{peak_hour_heat}:00</b> hours, with total spending reaching <b>₹{heat_amt}</b> during that time slot.
                            </div>
                            """, unsafe_allow_html=True)

                    elif selection == "📉 Daily Trends":
                        header_with_info_inline("Daily Spending Trend", "Line chart showing daily total spending over time.")
                        daily_f = filtered_df.groupby('date')['amount'].sum().reset_index()
                        st.plotly_chart(px.line(daily_f, x='date', y='amount'), use_container_width=True)
                    
                    elif selection == "🕒 Hourly Spend":
                        header_with_info_inline("Spending by Hour", "How your spending varies across hours of the day.")
                        hourly_f = filtered_df.groupby('hour')['amount'].sum().reset_index()
                        st.plotly_chart(px.bar(hourly_f, x='hour', y='amount'), use_container_width=True)

                    elif selection == "🗓️ Weekly Category":
                        header_with_info_inline("Category-wise Weekly Spending", "Stacked bar showing each category's spend across weekdays.")
                        weekly_cat_f = filtered_df.groupby(['day', 'category'])['amount'].sum().reset_index()
                        st.plotly_chart(px.bar(weekly_cat_f, x='day', y='amount', color='category', barmode='stack'), use_container_width=True)

        with tab2:
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
                        st.error("❌ Something went wrong during chatbot interaction. Please try again.")
            elif user_question:
                st.warning("Please set your OPENROUTER_API_KEY in .env to enable chatbot.")

        # After loading df from the database, show a compact transaction viewer
        if data_source == "Connect to UPI (dummy simulation)":
            with st.expander("Live UPI Transactions (latest on top)", expanded=False):
                if not df.empty:
                    st.dataframe(df.sort_values('timestamp', ascending=False).reset_index(drop=True), height=200, use_container_width=True)
                else:
                    st.info("No transactions yet.")

    except Exception as e:
        st.error("❌ Something went wrong while processing the file. Please check the format and try again.")
else:
    col1, col2 = st.columns([6, 1])

    with col1:
        st.info("⬆️ Please upload a transaction CSV or connect to UPI simulation to begin.")

    with col2:
        with st.popover("🧾 Sample format"):
            st.markdown("Your file must include the following columns:")
            st.code("date,time,amount,merchant,txn_type,category,city", language='csv')
            sample_df = pd.DataFrame({
                "date": ["2025-07-01"],
                "time": ["10:30:00"],
                "amount": [349],
                "merchant": ["Jio"],
                "txn_type": ["debit"],
                "category": ["Recharge"],
                "city": ["Pune"]
            })
            st.dataframe(sample_df, use_container_width=True)