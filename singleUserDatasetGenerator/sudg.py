import os
import random
import uuid
from datetime import datetime, timedelta
import pandas as pd

# Default city for student transactions
NORMAL_CITY = "Pune"

# Category-Merchant mapping (Recharge added)
CATEGORIES = {
    'Education': ['Byjus', 'Unacademy', 'Vedantu'],
    'Food': ['Swiggy', 'Zomato', 'Dominos'],
    'Entertainment': ['Netflix', 'BookMyShow', 'Hotstar'],
    'Books': ['Amazon', 'Flipkart', 'Kindle'],
    'Transport': ['Ola', 'Uber', 'IRCTC'],
    'Recharge': ['Jio', 'Airtel', 'Vi', 'BSNL']  # ✅ New Recharge category
}

# Recharge plans for known merchants (₹ amount ~ 28-day validity)
RECHARGE_PLANS = {
    'Jio': [149, 199, 239, 299, 349, 399],
    'Airtel': [199, 239, 299, 349, 399],
    'Vi': [179, 199, 269, 299],
    'BSNL': [187, 247, 319, 399]
}

PAYMENT_MODES = ['UPI', 'Card', 'Netbanking', 'Cash']
UNUSUAL_CITIES = ['Shimla', 'Goa', 'Leh', 'Gangtok']

def random_time():
    hour = random.randint(8, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"{hour:02}:{minute:02}:{second:02}"

def generate_student_transactions(num_txns=1000):
    start_date = datetime.now() - timedelta(days=210)
    transactions = []

    for _ in range(num_txns):
        txn_date = start_date + timedelta(days=random.randint(0, 210))
        txn_time = random_time()
        
        # Bias Recharge to ~5% probability
        category = random.choices(
            population=list(CATEGORIES.keys()),
            weights=[20, 25, 20, 10, 15, 10],  # Recharge = 10/100 = 10%
            k=1
        )[0]

        merchant = random.choice(CATEGORIES[category])
        payment_mode = random.choice(PAYMENT_MODES)

        # Amount generation logic
        if category == 'Recharge':
            amount = random.choice(RECHARGE_PLANS[merchant])
        elif category == 'Education':
            amount = random.randint(1000, 2500)
        elif category == 'Books':
            amount = random.randint(400, 1800)
        else:
            amount = random.randint(100, 1500)

        txn_type = 'debit'  # All spending transactions

        transactions.append([
            str(uuid.uuid4()), txn_date.strftime('%Y-%m-%d'), txn_time,
            category, merchant, amount, txn_type, payment_mode, NORMAL_CITY
        ])

    return transactions

def inject_anomalies(transactions):
    df = pd.DataFrame(transactions, columns=[
        'transaction_id', 'date', 'time', 'category', 'merchant',
        'amount', 'txn_type', 'payment_mode', 'city'
    ])

    # 🟡 Duplicate Transactions (1%) with 2–3 min time difference
    duplicates = df.sample(frac=0.01, random_state=42)
    for _, row in duplicates.iterrows():
        orig_time = datetime.strptime(row['time'], '%H:%M:%S')
        new_time = (orig_time + timedelta(minutes=random.randint(1, 3))).time()
        row_copy = row.copy()
        row_copy['transaction_id'] = str(uuid.uuid4())
        row_copy['time'] = new_time.strftime('%H:%M:%S')
        df = pd.concat([df, pd.DataFrame([row_copy])], ignore_index=True)

    # 🔺 Payment Spikes (1%)
    spikes = df.sample(frac=0.01, random_state=1)
    for i in spikes.index:
        df.at[i, 'amount'] *= 10

    # 🌍 Out-of-City Expenses (1%)
    out_city_txns = df.sample(frac=0.01, random_state=3)
    for i in out_city_txns.index:
        df.at[i, 'city'] = random.choice(UNUSUAL_CITIES)

    df = df.sample(frac=1).reset_index(drop=True)
    return df

def main():
    os.makedirs('dataset', exist_ok=True)
    base_txns = generate_student_transactions(num_txns=1000)
    final_df = inject_anomalies(base_txns)
    final_df.to_csv('dataset/sample_student_transactions.csv', index=False)
    print("✅ Generated dataset/sample_student_transactions.csv with Recharge category and anomalies.")

if __name__ == "__main__":
    main()
