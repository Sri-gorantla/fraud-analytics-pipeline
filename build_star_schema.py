import pandas as pd

df = pd.read_csv('cleaned_transactions_flat.csv', parse_dates=['transaction_datetime'])

# dim_customer - now includes tenure_months and risk_segment as originally designed
dim_customer = df[['customer_id','account_type','customer_home_country',
                    'customer_tenure_months','customer_risk_segment']].drop_duplicates().reset_index(drop=True)
dim_customer.columns = ['customer_id','account_type','home_country','tenure_months','risk_segment']
print('dim_customer rows:', len(dim_customer))

# dim_merchant - now includes merchant_risk_tier as originally designed
dim_merchant = df[['merchant_id','merchant_category','merchant_risk_tier']].drop_duplicates().reset_index(drop=True)
merch_country = df.groupby('merchant_id')['transaction_country'].agg(lambda x: x.mode()[0]).reset_index()
merch_country.columns = ['merchant_id','merchant_country']
dim_merchant = dim_merchant.merge(merch_country, on='merchant_id')
dim_merchant.columns = ['merchant_id','category','risk_tier','country']
print('dim_merchant rows:', len(dim_merchant))

dim_location = pd.DataFrame({'country': sorted(df['transaction_country'].unique())})
dim_location['location_id'] = ['LOC' + str(i+1).zfill(3) for i in range(len(dim_location))]
dim_location = dim_location[['location_id','country']]

dim_channel = pd.DataFrame({'channel_type': sorted(df['channel'].unique())})
dim_channel['channel_id'] = ['CH' + str(i+1).zfill(2) for i in range(len(dim_channel))]
dim_channel = dim_channel[['channel_id','channel_type']]

dates = pd.DataFrame({'full_date': sorted(df['transaction_datetime'].dt.date.unique())})
dates['full_date'] = pd.to_datetime(dates['full_date'])
dates['date_id'] = dates['full_date'].dt.strftime('%Y%m%d')
dates['month'] = dates['full_date'].dt.month
dates['quarter'] = dates['full_date'].dt.quarter
dates['day_of_week'] = dates['full_date'].dt.day_name()
dates['is_weekend'] = dates['full_date'].dt.dayofweek >= 5
dim_date = dates[['date_id','full_date','month','quarter','day_of_week','is_weekend']]

fact = df.copy()
fact['date_id'] = fact['transaction_datetime'].dt.strftime('%Y%m%d')
fact['transaction_time'] = fact['transaction_datetime'].dt.strftime('%H:%M:%S')
fact = fact.merge(dim_location, left_on='transaction_country', right_on='country')
fact = fact.merge(dim_channel, left_on='channel', right_on='channel_type')

fact_transactions = fact[['transaction_id','customer_id','merchant_id','location_id','channel_id',
                            'date_id','transaction_time','amount']]

print('dim_location rows:', len(dim_location), '| dim_channel rows:', len(dim_channel), '| dim_date rows:', len(dim_date))
print('fact_transactions rows:', len(fact_transactions))
print()
print('dim_customer sample:')
print(dim_customer.head(3).to_string())
print()
print('dim_merchant sample:')
print(dim_merchant.head(3).to_string())

dim_customer.to_csv('dim_customer.csv', index=False)
dim_merchant.to_csv('dim_merchant.csv', index=False)
dim_location.to_csv('dim_location.csv', index=False)
dim_channel.to_csv('dim_channel.csv', index=False)
dim_date.to_csv('dim_date.csv', index=False)
fact_transactions.to_csv('fact_transactions.csv', index=False)
