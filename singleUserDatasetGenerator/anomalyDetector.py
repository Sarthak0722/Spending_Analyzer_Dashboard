import pandas as pd
from datetime import datetime, timedelta

# --- Recharge validity mapping based on amount ---
RECHARGE_VALIDITY = {
    149: 20, 199: 28, 239: 28, 299: 28, 349: 28, 399: 28,
    179: 28, 269: 28,
    187: 28, 247: 28, 319: 28
}

# Load the CSV
df = pd.read_csv('dataset/sample_student_transactions.csv')

# Convert date and time columns to datetime
df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])

# Detect Duplicate Payments (within 3 minutes)
def detect_duplicates(df):
    df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
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
                current['amount'] == candidate['amount']
                and current['merchant'] == candidate['merchant']
                and current['txn_type'] == candidate['txn_type']
                and current['payment_mode'] == candidate['payment_mode']
                and current['city'] == candidate['city']
            ):
                duplicate_indices.add(current['index'])
                duplicate_indices.add(candidate['index'])

    return df.loc[list(duplicate_indices)].sort_values('timestamp')

# Detect Spike Transactions (10× median)
def detect_spikes(df):
    median_amt = df['amount'].median()
    spikes = df[df['amount'] > 10 * median_amt]
    return spikes

# Detect Out-of-City Transactions
def detect_out_of_city(df, base_city="Pune"):
    return df[df['city'] != base_city]

# ✅ Detect all currently valid recharges and their due dates
def detect_current_recharge(df):
    recharge_df = df[df['category'] == 'Recharge'].sort_values('timestamp', ascending=False)
    active_recharges = []

    for _, row in recharge_df.iterrows():
        amount = row['amount']
        if amount in RECHARGE_VALIDITY:
            validity_days = RECHARGE_VALIDITY[amount]
            start_date = row['timestamp']
            end_date = start_date + timedelta(days=validity_days)

            if end_date > datetime.now():
                # Skip if already added newer recharge from the same merchant
                already_tracked = any(
                    r['merchant'] == row['merchant'] and r['start_date'] >= start_date
                    for r in active_recharges
                )
                if not already_tracked:
                    active_recharges.append({
                        'start_date': start_date,
                        'end_date': end_date,
                        'merchant': row['merchant'],
                        'amount': amount,
                        'validity_days': validity_days
                    })

    return active_recharges

# Run detection
duplicate_txns = detect_duplicates(df)
spike_txns = detect_spikes(df)
out_city_txns = detect_out_of_city(df)
current_recharges = detect_current_recharge(df)

# Print results
print("\n🔁 Duplicate Transactions (within 3 minutes):")
print(duplicate_txns[['timestamp', 'merchant', 'amount', 'payment_mode', 'city']])

print("\n💥 Spike Transactions (10× median):")
print(spike_txns[['timestamp', 'merchant', 'amount', 'payment_mode', 'city']])

print("\n🌍 Out-of-City Transactions:")
print(out_city_txns[['timestamp', 'merchant', 'amount', 'payment_mode', 'city']])

# Print Recharge Status
if current_recharges:
    print("\n📲 Currently Active Recharges:")
    for r in current_recharges:
        print(f"- {r['merchant']} ₹{r['amount']} | Started: {r['start_date'].strftime('%Y-%m-%d')} | "
              f"Valid for {r['validity_days']} days | Ends: {r['end_date'].strftime('%Y-%m-%d')}")
else:
    print("\n⚠️ No currently valid recharge found.")
