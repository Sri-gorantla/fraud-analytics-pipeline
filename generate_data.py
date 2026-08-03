import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

np.random.seed(7)
random.seed(7)

N_CUSTOMERS = 800
N_MERCHANTS = 150

customer_ids = [f"CUST{10000+i}" for i in range(N_CUSTOMERS)]
merchant_ids = [f"MER{2000+i}" for i in range(N_MERCHANTS)]

countries = ['UK', 'Germany', 'Ireland', 'USA', 'France', 'Spain']
merchant_categories = ['Groceries', 'Electronics', 'Travel', 'Dining', 'Fashion', 'Fuel', 'Entertainment', 'Online Retail']
channels = ['Online', 'POS', 'ATM']
risk_segments = ['Low', 'Medium', 'High']

customer_profile = {
    cid: {
        'home_country': random.choice(countries),
        'avg_spend': round(np.random.uniform(15, 150), 2),
        'account_type': random.choice(['Current', 'Savings', 'Premium']),
        'tenure_months': random.randint(1, 96),
        # risk segment weighted realistically - most customers are Low/Medium risk
        'risk_segment': random.choices(risk_segments, weights=[0.6, 0.3, 0.1])[0]
    }
    for cid in customer_ids
}
merchant_profile = {
    mid: {
        'category': random.choice(merchant_categories),
        'country': random.choice(countries),
        'risk_tier': random.choices(risk_segments, weights=[0.55, 0.30, 0.15])[0]
    }
    for mid in merchant_ids
}

START_DATE = datetime(2025, 6, 1)
N_DAYS = 60

rows = []
txn_counter = 0
customer_seen_merchants = {cid: set() for cid in customer_ids}

def make_txn(cust, merch, dt, amount, channel, is_fraud, fraud_type=None):
    global txn_counter
    txn_counter += 1
    loc_country = merchant_profile[merch]['country']
    return {
        'transaction_id': f"TXN{txn_counter:07d}",
        'customer_id': cust,
        'merchant_id': merch,
        'merchant_category': merchant_profile[merch]['category'],
        'merchant_risk_tier': merchant_profile[merch]['risk_tier'],
        'transaction_country': loc_country,
        'channel': channel,
        'transaction_datetime': dt,
        'amount': round(amount, 2),
        'account_type': customer_profile[cust]['account_type'],
        'customer_home_country': customer_profile[cust]['home_country'],
        'customer_tenure_months': customer_profile[cust]['tenure_months'],
        'customer_risk_segment': customer_profile[cust]['risk_segment'],
        'is_fraud': is_fraud,
        'fraud_type': fraud_type if is_fraud else None
    }

for day in range(N_DAYS):
    day_date = START_DATE + timedelta(days=day)
    daily_txn_count = np.random.randint(180, 260)

    for _ in range(daily_txn_count):
        cust = random.choice(customer_ids)
        merch = random.choice(merchant_ids)
        profile = customer_profile[cust]
        hour = np.random.choice(range(7, 23))
        dt = day_date + timedelta(hours=int(hour), minutes=random.randint(0,59))
        amount = max(2, np.random.normal(profile['avg_spend'], profile['avg_spend']*0.4))
        channel = np.random.choice(channels, p=[0.45, 0.45, 0.10])
        customer_seen_merchants[cust].add(merch)
        rows.append(make_txn(cust, merch, dt, amount, channel, is_fraud=False))

    if np.random.rand() < 0.35:
        cust = random.choice(customer_ids)
        base_dt = day_date + timedelta(hours=random.randint(0,23), minutes=random.randint(0,30))
        for k in range(random.randint(5,8)):
            merch = random.choice(merchant_ids)
            dt = base_dt + timedelta(minutes=k*3)
            rows.append(make_txn(cust, merch, dt, np.random.uniform(1,20), 'Online', True, 'velocity'))

    if np.random.rand() < 0.30:
        cust = random.choice(customer_ids)
        foreign_merchants = [m for m in merchant_ids if merchant_profile[m]['country'] != customer_profile[cust]['home_country']]
        merch = random.choice(foreign_merchants)
        dt = day_date + timedelta(hours=random.randint(0,23), minutes=random.randint(0,59))
        rows.append(make_txn(cust, merch, dt, np.random.uniform(50,400), 'POS', True, 'geo_mismatch'))

    if np.random.rand() < 0.30:
        cust = random.choice(customer_ids)
        merch = random.choice(merchant_ids)
        dt = day_date + timedelta(hours=random.randint(0,23), minutes=random.randint(0,59))
        amt = customer_profile[cust]['avg_spend'] * np.random.uniform(8, 15)
        rows.append(make_txn(cust, merch, dt, amt, 'Online', True, 'amount_anomaly'))

    if np.random.rand() < 0.25:
        cust = random.choice(customer_ids)
        merch = random.choice(merchant_ids)
        dt = day_date + timedelta(hours=random.randint(2,4), minutes=random.randint(0,59))
        rows.append(make_txn(cust, merch, dt, np.random.uniform(30,200), 'Online', True, 'odd_hour'))

    if np.random.rand() < 0.25:
        cust = random.choice(customer_ids)
        unseen = [m for m in merchant_ids if m not in customer_seen_merchants[cust]]
        if unseen:
            merch = random.choice(unseen)
            dt = day_date + timedelta(hours=random.randint(0,23), minutes=random.randint(0,59))
            amt = customer_profile[cust]['avg_spend'] * np.random.uniform(6,10)
            rows.append(make_txn(cust, merch, dt, amt, 'Online', True, 'new_merchant_high_value'))

print(f"Generated {len(rows)} transactions across {N_DAYS} simulated days")
print(f"Fraud rate: {sum(1 for r in rows if r['is_fraud'])/len(rows)*100:.2f}%")

df = pd.DataFrame(rows)
df.to_csv('all_transactions_clean_reference.csv', index=False)
print('New columns added:', ['merchant_risk_tier','customer_tenure_months','customer_risk_segment'])
