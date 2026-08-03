import duckdb

con = duckdb.connect('fraud_warehouse.duckdb')

# Create tables with explicit types and PRIMARY/FOREIGN KEY constraints -
# same intent as Redshift: declare relationships even though Redshift itself
# doesn't strictly enforce FKs at runtime (per Part 8's note - it documents intent
# and helps BI tools understand the model)

con.execute("DROP TABLE IF EXISTS fact_transactions")
con.execute("DROP TABLE IF EXISTS dim_customer")
con.execute("DROP TABLE IF EXISTS dim_merchant")
con.execute("DROP TABLE IF EXISTS dim_location")
con.execute("DROP TABLE IF EXISTS dim_channel")
con.execute("DROP TABLE IF EXISTS dim_date")

con.execute("""
CREATE TABLE dim_customer (
    customer_id VARCHAR PRIMARY KEY,
    account_type VARCHAR,
    home_country VARCHAR,
    tenure_months INTEGER,
    risk_segment VARCHAR
)
""")
con.execute("""
CREATE TABLE dim_merchant (
    merchant_id VARCHAR PRIMARY KEY,
    category VARCHAR,
    risk_tier VARCHAR,
    country VARCHAR
)
""")
con.execute("""
CREATE TABLE dim_location (
    location_id VARCHAR PRIMARY KEY,
    country VARCHAR
)
""")
con.execute("""
CREATE TABLE dim_channel (
    channel_id VARCHAR PRIMARY KEY,
    channel_type VARCHAR
)
""")
con.execute("""
CREATE TABLE dim_date (
    date_id VARCHAR PRIMARY KEY,
    full_date DATE,
    month INTEGER,
    quarter INTEGER,
    day_of_week VARCHAR,
    is_weekend BOOLEAN
)
""")
con.execute("""
CREATE TABLE fact_transactions (
    transaction_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR REFERENCES dim_customer(customer_id),
    merchant_id VARCHAR REFERENCES dim_merchant(merchant_id),
    location_id VARCHAR REFERENCES dim_location(location_id),
    channel_id VARCHAR REFERENCES dim_channel(channel_id),
    date_id VARCHAR REFERENCES dim_date(date_id),
    transaction_time VARCHAR,
    amount DECIMAL(12,2)
)
""")

# Load each CSV directly into its table
for table, file in [
    ('dim_customer', 'dim_customer.csv'),
    ('dim_merchant', 'dim_merchant.csv'),
    ('dim_location', 'dim_location.csv'),
    ('dim_channel', 'dim_channel.csv'),
    ('dim_date', 'dim_date.csv'),
    ('fact_transactions', 'fact_transactions.csv'),
]:
    con.execute(f"INSERT INTO {table} SELECT * FROM read_csv_auto('{file}')")
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table}: {count} rows loaded")

con.close()
print()
print("Warehouse file created: fraud_warehouse.duckdb")
