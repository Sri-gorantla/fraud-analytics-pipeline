import pandas as pd
import numpy as np
import glob

files = glob.glob('s3_raw_zone/transactions/dt=*/transactions_export.csv')
df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
print('Starting rows:', len(df))

for col in ['channel', 'merchant_category', 'transaction_country', 'customer_home_country', 'account_type',
            'merchant_risk_tier', 'customer_risk_segment']:
    df[col] = df[col].astype(str).str.strip().str.title()
    df.loc[df[col] == 'Nan', col] = np.nan

def parse_mixed(s):
    s = str(s).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M'):
        try:
            return pd.to_datetime(s, format=fmt)
        except ValueError:
            continue
    return pd.NaT
df['transaction_datetime'] = df['transaction_datetime'].apply(parse_mixed)

median_amount = df['amount'].median()
df['amount'] = df['amount'].fillna(median_amount)

merchant_country_map = df.dropna(subset=['transaction_country']).groupby('merchant_id')['transaction_country'].agg(lambda x: x.mode()[0])
mask = df['transaction_country'].isna()
df.loc[mask, 'transaction_country'] = df.loc[mask, 'merchant_id'].map(merchant_country_map)

df['merchant_category'] = df['merchant_category'].fillna('Unknown')

# NEW: missing customer_tenure_months -> recoverable via customer_id lookup (fixed per customer)
tenure_map = df.dropna(subset=['customer_tenure_months']).groupby('customer_id')['customer_tenure_months'].first()
mask_t = df['customer_tenure_months'].isna()
df.loc[mask_t, 'customer_tenure_months'] = df.loc[mask_t, 'customer_id'].map(tenure_map)
print('Tenure still missing after recovery:', df['customer_tenure_months'].isna().sum())

# acronym fix
acronym_fix = {'Usa': 'USA', 'Uk': 'UK'}
for col in ['transaction_country', 'customer_home_country']:
    df[col] = df[col].replace(acronym_fix)

neg_mask = df['amount'] < 0
df.loc[neg_mask, 'amount'] = df.loc[neg_mask, 'amount'].abs()
cust_avg = df.groupby('customer_id')['amount'].transform('median')
likely_entry_error = df['amount'] > (cust_avg * 50)
df.loc[likely_entry_error, 'amount'] = df.loc[likely_entry_error, 'amount'] / 100

before = len(df)
df = df.drop_duplicates(subset=['transaction_id'], keep='first')
print('Duplicates removed:', before - len(df))

# recover true merchant_category ignoring Unknown
real_cat = df[df['merchant_category']!='Unknown'].groupby('merchant_id')['merchant_category'].agg(lambda x: x.mode()[0])
df['merchant_category'] = df['merchant_id'].map(real_cat).fillna('Unknown')

# recover true merchant_risk_tier the same way (should be fixed per merchant)
real_risk = df.groupby('merchant_id')['merchant_risk_tier'].agg(lambda x: x.mode()[0])
df['merchant_risk_tier'] = df['merchant_id'].map(real_risk)

# recover true customer_risk_segment the same way (fixed per customer)
real_cust_risk = df.groupby('customer_id')['customer_risk_segment'].agg(lambda x: x.mode()[0])
df['customer_risk_segment'] = df['customer_id'].map(real_cust_risk)

print()
print('FINAL SHAPE:', df.shape)
print('Missing % per column:')
print((df.isnull().mean()*100).round(2))
df.to_csv('cleaned_transactions_flat.csv', index=False)
