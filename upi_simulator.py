import sqlite3
import random
import uuid
from datetime import datetime, timedelta
import time

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
NORMAL_CITY = "Pune"
UNUSUAL_CITIES = ['Shimla', 'Goa', 'Leh', 'Gangtok']

def random_time():
    now = datetime.now()
    return now.strftime('%H:%M:%S')

def create_db():
    conn = sqlite3.connect('simulated_transactions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        date TEXT,
        time TEXT,
        amount REAL,
        merchant TEXT,
        txn_type TEXT,
        category TEXT,
        city TEXT
    )''')
    conn.commit()
    conn.close()

def generate_transaction():
    is_credit = random.random() < 0.15  # ~15% are credit transactions
    if is_credit:
        category = "Income"
        merchant = random.choice(["Mom", "Dad", "Scholarship", "Friend Refund"])
        amount = random.randint(300, 6000)
        txn_type = "credit"
    else:
        is_person_merchant = random.random() < 0.25
        if is_person_merchant:
            merchant = random.choice(PERSON_MERCHANTS)
            category = "Friends/Vendor"
        else:
            category = random.choices(
                population=list(CATEGORIES.keys()),
                weights=[10, 25, 15, 10, 10, 10],
                k=1
            )[0]
            merchant = random.choice(CATEGORIES[category])
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
    # 1% chance for out-of-city
    city = NORMAL_CITY
    if txn_type == 'debit' and random.random() < 0.01:
        city = random.choice(UNUSUAL_CITIES)
    now = datetime.now()
    return [
        str(uuid.uuid4()),
        now.strftime('%Y-%m-%d'),
        random_time(),
        amount,
        merchant,
        txn_type,
        category,
        city
    ]

def insert_transaction(txn):
    conn = sqlite3.connect('simulated_transactions.db')
    c = conn.cursor()
    c.execute('''INSERT INTO transactions (transaction_id, date, time, amount, merchant, txn_type, category, city)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', txn)
    conn.commit()
    conn.close()

def main():
    create_db()
    print("Simulating UPI transactions. Press Ctrl+C to stop.")
    while True:
        txn = generate_transaction()
        insert_transaction(txn)
        print(f"Generated transaction: {txn}")
        time.sleep(10)

if __name__ == "__main__":
    main() 