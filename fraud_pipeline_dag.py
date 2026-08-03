"""
Fraud & Risk Analytics Pipeline - Daily Orchestration DAG

Pipeline: extract -> clean -> build_star_schema -> load_warehouse -> quality_check

Design decisions (per Part 3 ADR + Part 9 of the playbook):
- Each step is a SEPARATE task, not one big script, so failures are isolated
  and retryable at the exact step that broke (Part 9.1)
- extract/clean/build_star_schema are safe to rerun freely - they fully overwrite
  their output each time, no accumulation
- load_warehouse is NOT safe to rerun with a plain INSERT - we use
  "delete matching keys, then insert" so reruns never create duplicates
- quality_check runs LAST and is read-only - if it fails, the bad data is already
  loaded, so a real production version would also alert/rollback here (noted as
  a known limitation of this first version, not something we've built yet)
"""

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "sri_harsha",
    "retries": 2,                        # transient failures (e.g. a locked file) get retried automatically
    "retry_delay": timedelta(minutes=2),
}

def extract_daily_file(**context):
    """Simulates picking up today's raw batch file from the S3 raw zone (Part 6)."""
    import glob
    ds = context["ds"]  # Airflow's built-in run date, e.g. '2025-06-15'
    path = f"s3_raw_zone/transactions/dt={ds}/transactions_export.csv"
    files = glob.glob(path)
    if not files:
        raise FileNotFoundError(f"No raw file found for {ds} - upstream export may be late")
    print(f"Found raw file: {files[0]}")

def clean_data(**context):
    """Runs the Part 7 cleaning logic. Safe to rerun - overwrites its output file completely."""
    import subprocess
    subprocess.run(["python3", "clean_transform.py"], check=True, cwd="/home/claude/fraud_project")

def build_star_schema(**context):
    """Splits the cleaned flat file into fact_transactions + dimension tables (Part 7)."""
    import subprocess
    subprocess.run(["python3", "build_star_schema.py"], check=True, cwd="/home/claude/fraud_project")

def load_warehouse(**context):
    """
    Loads into the warehouse (Part 8) using DELETE-then-INSERT on transaction_id,
    NOT a plain append - this is exactly the idempotency fix we discussed:
    rerunning this task never creates duplicate fact rows.
    """
    import duckdb
    con = duckdb.connect("/home/claude/fraud_project/fraud_warehouse.duckdb")
    con.execute("""
        DELETE FROM fact_transactions
        WHERE transaction_id IN (SELECT transaction_id FROM read_csv_auto('/home/claude/fraud_project/fact_transactions.csv'))
    """)
    con.execute("INSERT INTO fact_transactions SELECT * FROM read_csv_auto('/home/claude/fraud_project/fact_transactions.csv')")
    count = con.execute("SELECT COUNT(*) FROM fact_transactions").fetchone()[0]
    print(f"fact_transactions now has {count} rows after idempotent load")
    con.close()

def quality_check(**context):
    """Read-only checks - safe to rerun any number of times, changes nothing."""
    import duckdb
    con = duckdb.connect("/home/claude/fraud_project/fraud_warehouse.duckdb", read_only=True)
    min_amount = con.execute("SELECT MIN(amount) FROM fact_transactions").fetchone()[0]
    null_customers = con.execute("SELECT COUNT(*) FROM fact_transactions WHERE customer_id IS NULL").fetchone()[0]
    con.close()

    assert min_amount >= 0, f"Quality check FAILED: negative amount found ({min_amount})"
    assert null_customers == 0, f"Quality check FAILED: {null_customers} rows missing customer_id"
    print("Quality checks passed: no negative amounts, no missing customer_id")


with DAG(
    dag_id="fraud_analytics_daily_pipeline",
    default_args=default_args,
    description="Daily ETL for the fraud & risk analytics warehouse",
    schedule="@daily",
    start_date=datetime(2025, 6, 1),
    catchup=False,
    tags=["fraud", "portfolio-project"],
) as dag:

    t1_extract = PythonOperator(task_id="extract_daily_file", python_callable=extract_daily_file)
    t2_clean = PythonOperator(task_id="clean_data", python_callable=clean_data)
    t3_schema = PythonOperator(task_id="build_star_schema", python_callable=build_star_schema)
    t4_load = PythonOperator(task_id="load_warehouse", python_callable=load_warehouse)
    t5_quality = PythonOperator(task_id="quality_check", python_callable=quality_check)

    # This line IS the dependency graph - the actual "D" and "A" in DAG
    t1_extract >> t2_clean >> t3_schema >> t4_load >> t5_quality
