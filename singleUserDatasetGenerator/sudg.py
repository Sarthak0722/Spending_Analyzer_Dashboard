import os
import random
import uuid
from datetime import datetime, timedelta
import pandas as pd

NORMAL_CITY = "Pune"

CATEGORIES = {
    'Education': ['Byjus', 'Unacademy', 'Vedantu'],
    'Food': ['Swiggy', 'Zomato', 'Dominos'],
    'Entertainment': ['Netflix', 'BookMyShow', 'Hotstar'],
    'Books': ['Amazon', 'Flipkart', 'Kindle'],
    'Transport': ['Ola', 'Uber', 'IRCTC'],
    'Recharge': ['Jio', 'Airtel', 'Vi', 'BSNL']
}

RECHARGE_PLANS = {
    'Jio': [149, 199, 239, 299, 349, 399],
    'Airtel': [199, 239, 299, 349, 399],
    'Vi': [179, 199, 269, 299],
    'BSNL': [187, 247, 319, 399]
}

PERSON_MERCHANTS = ["Mom", "Dad", "Ramesh Veggie", "Ankita", "Ajay", "Local Kirana", "Street Vendor"]
UNUSUAL_CITIES = ['Shimla', 'Goa', 'Leh', 'Gangtok']

def random_time():
    hour = random.randint(8, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"{hour:02}:{minute:02}:{second:02}"

def generate_transactions_over_10_months():
    today = datetime.now()
    start_date = today - timedelta(days=300)
    transactions = []

    current_date = start_date
    while current_date <= today:
        month = current_date.month
        year = current_date.year

        # -- Recharge Control --
        recharge_count = 0

        # Random number of transactions this month (15–40)
        num_txns = random.randint(15, 40)

        for _ in range(num_txns):
            txn_date = current_date + timedelta(days=random.randint(0, 27))
            txn_time = random_time()
            is_credit = random.random() < 0.15  # ~15% are credit transactions

            if is_credit:
                # CREDIT TRANSACTIONS
                category = "Income"
                merchant = random.choice(["Mom", "Dad", "Scholarship", "Friend Refund"])
                amount = random.randint(300, 6000)
                txn_type = "credit"
            else:
                # DEBIT TRANSACTIONS
                is_person_merchant = random.random() < 0.25
                if is_person_merchant:
                    merchant = random.choice(PERSON_MERCHANTS)
                    category = "Friends/Vendor"
                else:
                    category = random.choices(
                        population=list(CATEGORIES.keys()),
                        weights=[10, 25, 15, 10, 10, 10],  # Recharge weight reduced
                        k=1
                    )[0]

                    # Control recharge count per month
                    if category == "Recharge":
                        if recharge_count >= 2:
                            category = "Food"  # Replace with non-recharge
                            merchant = random.choice(CATEGORIES[category])
                        else:
                            merchant = random.choice(CATEGORIES[category])
                            recharge_count += 1
                    else:
                        merchant = random.choice(CATEGORIES[category])

                # Amount
                if category == 'Recharge':
                    amount = random.choice(RECHARGE_PLANS[merchant])
                elif category == 'Education':
                    amount = random.randint(500, 2500)
                elif category == 'Books':
                    amount = random.randint(100, 1800)
                elif category == 'Friends/Vendor':
                    amount = random.randint(10, 1500)
                else:
                    amount = random.randint(1, 3000)

                txn_type = 'debit'

            transactions.append([
                str(uuid.uuid4()), txn_date.strftime('%Y-%m-%d'), txn_time,
                category, merchant, amount, txn_type, NORMAL_CITY
            ])

        # Move to next month
        current_date = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)

    return transactions

def inject_anomalies(transactions):
    df = pd.DataFrame(transactions, columns=[
        'transaction_id', 'date', 'time', 'category', 'merchant',
        'amount', 'txn_type', 'city'
    ])

    # 🔁 Add 3 duplicate transactions with minor time difference
    duplicates = df[df['txn_type'] == 'debit'].sample(n=3, random_state=42)
    for _, row in duplicates.iterrows():
        orig_time = datetime.strptime(row['time'], '%H:%M:%S')
        new_time = (orig_time + timedelta(minutes=random.randint(1, 3))).time()
        row_copy = row.copy()
        row_copy['transaction_id'] = str(uuid.uuid4())
        row_copy['time'] = new_time.strftime('%H:%M:%S')
        df = pd.concat([df, pd.DataFrame([row_copy])], ignore_index=True)

    # 🔺 Payment spikes (~1%) only for debit
    spikes = df[df['txn_type'] == 'debit'].sample(frac=0.01, random_state=1)
    for i in spikes.index:
        df.at[i, 'amount'] = min(df.at[i, 'amount'] * 10, 25000)

    # 🌍 Out-of-city (~1%) for debit
    out_city_txns = df[df['txn_type'] == 'debit'].sample(frac=0.01, random_state=2)
    for i in out_city_txns.index:
        df.at[i, 'city'] = random.choice(UNUSUAL_CITIES)

    return df.sample(frac=1).reset_index(drop=True)

def main():
    os.makedirs('dataset', exist_ok=True)
    txns = generate_transactions_over_10_months()
    final_df = inject_anomalies(txns)
    final_df.to_csv('dataset/sample_student_transactions.csv', index=False)
    print("✅ Realistic 10-month student CSV generated at dataset/sample_student_transactions.csv")

if __name__ == "__main__":
    main()
