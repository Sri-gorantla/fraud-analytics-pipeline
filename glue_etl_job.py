"""
AWS Glue ETL Job: Fraud Analytics - Clean & Build Star Schema
Mirrors the proven local logic from clean_transform.py + build_star_schema.py,
now running as a real PySpark job against the Glue Data Catalog.
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# --- Job boilerplate (standard for every Glue job) ---
args = getResolvedOptions(sys.argv, ['JOB_NAME'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

CURATED_PATH = "s3://fraud-analytics-sri/curated"

# --- Read from the Glue Data Catalog (created by our crawler) ---
df = glueContext.create_dynamic_frame.from_catalog(
    database="fraud_analytics_db",
    table_name="transactions"
).toDF()

print(f"Starting rows: {df.count()}")

# --- 1. Standardize casing/whitespace on categorical columns ---
categorical_cols = ['channel', 'merchant_category', 'transaction_country',
                     'customer_home_country', 'account_type',
                     'merchant_risk_tier', 'customer_risk_segment']
for c in categorical_cols:
    df = df.withColumn(c, F.initcap(F.trim(F.col(c))))

# --- 2. Parse mixed date formats (YYYY-MM-DD HH:MM:SS and DD/MM/YYYY HH:MM) ---
df = df.withColumn(
    "transaction_ts",
    F.coalesce(
        F.to_timestamp("transaction_datetime", "yyyy-MM-dd HH:mm:ss"),
        F.to_timestamp("transaction_datetime", "dd/MM/yyyy HH:mm")
    )
)

# --- 3. Missing amount: confirmed MCAR locally -> fill with median ---
median_amount = df.approxQuantile("amount", [0.5], 0.01)[0]
df = df.withColumn("amount", F.coalesce(F.col("amount"), F.lit(median_amount)))

# --- 4. Missing transaction_country: recover via merchant lookup (most common
#         country seen for that merchant elsewhere in the data) ---
merchant_country = (
    df.filter(F.col("transaction_country").isNotNull())
    .groupBy("merchant_id", "transaction_country")
    .count()
    .withColumn("rn", F.row_number().over(
        Window.partitionBy("merchant_id").orderBy(F.desc("count"))))
    .filter(F.col("rn") == 1)
    .select("merchant_id", F.col("transaction_country").alias("merchant_country_lookup"))
)
df = df.join(merchant_country, on="merchant_id", how="left")
df = df.withColumn("transaction_country",
                    F.coalesce(F.col("transaction_country"), F.col("merchant_country_lookup")))
df = df.drop("merchant_country_lookup")

# --- 5. Acronym fix (Title-case breaks USA/UK) ---
df = df.withColumn("transaction_country",
    F.when(F.col("transaction_country") == "Usa", "USA")
     .when(F.col("transaction_country") == "Uk", "UK")
     .otherwise(F.col("transaction_country")))
df = df.withColumn("customer_home_country",
    F.when(F.col("customer_home_country") == "Usa", "USA")
     .when(F.col("customer_home_country") == "Uk", "UK")
     .otherwise(F.col("customer_home_country")))

# --- 6. Missing customer_tenure_months: recover via customer_id lookup ---
tenure_lookup = (
    df.filter(F.col("customer_tenure_months").isNotNull())
    .groupBy("customer_id")
    .agg(F.first("customer_tenure_months").alias("tenure_lookup"))
)
df = df.join(tenure_lookup, on="customer_id", how="left")
df = df.withColumn("customer_tenure_months",
                    F.coalesce(F.col("customer_tenure_months"), F.col("tenure_lookup")))
df = df.drop("tenure_lookup")

# --- 7. Fix negative amounts (sign errors) ---
df = df.withColumn("amount", F.abs(F.col("amount")))

# --- 8. Fix extreme entry errors (50x+ customer median -> divide by 100) ---
cust_median = df.groupBy("customer_id").agg(F.expr("percentile_approx(amount, 0.5)").alias("cust_median"))
df = df.join(cust_median, on="customer_id", how="left")
df = df.withColumn("amount",
    F.when(F.col("amount") > F.col("cust_median") * 50, F.col("amount") / 100)
     .otherwise(F.col("amount")))
df = df.drop("cust_median")

# --- 9. Deduplicate by transaction_id (keep first) ---
w = Window.partitionBy("transaction_id").orderBy(F.lit(1))
df = df.withColumn("rn", F.row_number().over(w)).filter(F.col("rn") == 1).drop("rn")

# --- 10. Recover true merchant_category and merchant_risk_tier via mode-per-merchant ---
def mode_per_key(df, key_col, value_col, exclude_value=None):
    filtered = df.filter(F.col(value_col).isNotNull())
    if exclude_value:
        filtered = filtered.filter(F.col(value_col) != exclude_value)
    ranked = (filtered.groupBy(key_col, value_col).count()
              .withColumn("rn", F.row_number().over(
                  Window.partitionBy(key_col).orderBy(F.desc("count"))))
              .filter(F.col("rn") == 1)
              .select(key_col, F.col(value_col).alias(f"{value_col}_mode")))
    return ranked

cat_mode = mode_per_key(df, "merchant_id", "merchant_category", exclude_value="Unknown")
df = df.join(cat_mode, on="merchant_id", how="left")
df = df.withColumn("merchant_category",
                    F.coalesce(F.col("merchant_category_mode"), F.lit("Unknown"))).drop("merchant_category_mode")

risk_mode = mode_per_key(df, "merchant_id", "merchant_risk_tier")
df = df.join(risk_mode, on="merchant_id", how="left")
df = df.withColumn("merchant_risk_tier", F.col("merchant_risk_tier_mode")).drop("merchant_risk_tier_mode")

cust_risk_mode = mode_per_key(df, "customer_id", "customer_risk_segment")
df = df.join(cust_risk_mode, on="customer_id", how="left")
df = df.withColumn("customer_risk_segment", F.col("customer_risk_segment_mode")).drop("customer_risk_segment_mode")

df.cache()
print(f"Final cleaned rows: {df.count()}")

# ============== BUILD STAR SCHEMA ==============

dim_customer = df.select("customer_id", "account_type", "customer_home_country",
                          "customer_tenure_months", "customer_risk_segment").distinct() \
    .withColumnRenamed("customer_home_country", "home_country") \
    .withColumnRenamed("customer_tenure_months", "tenure_months") \
    .withColumnRenamed("customer_risk_segment", "risk_segment")

dim_merchant = df.select("merchant_id", "merchant_category", "merchant_risk_tier",
                          "transaction_country").distinct() \
    .withColumnRenamed("merchant_category", "category") \
    .withColumnRenamed("merchant_risk_tier", "risk_tier") \
    .withColumnRenamed("transaction_country", "country") \
    .dropDuplicates(["merchant_id"])

dim_location = df.select("transaction_country").distinct() \
    .withColumnRenamed("transaction_country", "country") \
    .withColumn("location_id", F.concat(F.lit("LOC"), F.lpad(F.row_number().over(
        Window.orderBy("country")).cast("string"), 3, "0")))

dim_channel = df.select("channel").distinct() \
    .withColumnRenamed("channel", "channel_type") \
    .withColumn("channel_id", F.concat(F.lit("CH"), F.lpad(F.row_number().over(
        Window.orderBy("channel_type")).cast("string"), 2, "0")))

dim_date = df.select(F.to_date("transaction_ts").alias("full_date")).distinct() \
    .withColumn("date_id", F.date_format("full_date", "yyyyMMdd")) \
    .withColumn("month", F.month("full_date")) \
    .withColumn("quarter", F.quarter("full_date")) \
    .withColumn("day_of_week", F.date_format("full_date", "EEEE")) \
    .withColumn("is_weekend", F.dayofweek("full_date").isin([1, 7]))

fact = (df
    .withColumn("date_id", F.date_format(F.to_date("transaction_ts"), "yyyyMMdd"))
    .withColumn("transaction_time", F.date_format("transaction_ts", "HH:mm:ss"))
    .join(dim_location, df["transaction_country"] == dim_location["country"], "left")
    .join(dim_channel, df["channel"] == dim_channel["channel_type"], "left")
    .select("transaction_id", "customer_id", "merchant_id", "location_id",
            "channel_id", "date_id", "transaction_time", "amount"))

# --- Write curated star schema to S3 as Parquet (columnar, efficient - what Redshift COPY expects) ---
fact.write.mode("overwrite").parquet(f"{CURATED_PATH}/fact_transactions")
dim_customer.write.mode("overwrite").parquet(f"{CURATED_PATH}/dim_customer")
dim_merchant.write.mode("overwrite").parquet(f"{CURATED_PATH}/dim_merchant")
dim_location.write.mode("overwrite").parquet(f"{CURATED_PATH}/dim_location")
dim_channel.write.mode("overwrite").parquet(f"{CURATED_PATH}/dim_channel")
dim_date.write.mode("overwrite").parquet(f"{CURATED_PATH}/dim_date")

print("Star schema written to curated zone.")
job.commit()
