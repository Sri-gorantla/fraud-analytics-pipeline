# Fraud & Risk Analytics Pipeline

An end-to-end data pipeline that ingests simulated daily banking transaction exports,
cleans and models them into a star schema, loads them into a data warehouse, and
surfaces fraud-risk patterns through a BI dashboard — orchestrated on a daily schedule.

## Why this project exists
Built to close a specific gap: demonstrating hands-on cloud data engineering
(Glue/PySpark, Redshift, star schema modeling, orchestration) with a real working
pipeline, rather than listing the tools as "developing capabilities" without proof.
See `docs/project_brief.md` for full business framing.

## Architecture

```
Raw daily transaction exports (simulated bank export)
   │
   ▼  Land untouched, partitioned by date
S3 raw zone: s3_raw_zone/transactions/dt=YYYY-MM-DD/
   │
   ▼  Clean: standardize casing, parse mixed date formats, recover
   │  missing fields via lookup, fix data-entry errors, dedupe
clean_transform.py
   │
   ▼  Split into star schema
build_star_schema.py → fact_transactions + 5 dimension tables
   │
   ▼  Load (idempotent - delete-then-insert on transaction_id)
Data warehouse (DuckDB locally / Redshift in production)
   │
   ▼
Power BI dashboard
```

Orchestrated end-to-end by the Airflow DAG in `dags/fraud_pipeline_dag.py`
(schedule: `@daily`).

## Repo structure
```
docs/
  project_brief.md            - business context, questions, scope
  architecture_decisions.md   - every tool/design choice and why
  data_dictionary.md          - full schema documentation
  runbook.md                  - what to check when a pipeline task fails
dags/
  fraud_pipeline_dag.py       - Airflow orchestration
generate_data.py              - synthetic transaction + fraud pattern generator
clean_transform.py            - Part 7 cleaning logic
build_star_schema.py          - fact/dimension table construction
load_warehouse.py             - warehouse load logic
s3_raw_zone/                  - simulated raw landing zone (60 daily partitions)
fraud_warehouse.duckdb        - local warehouse (stand-in for Redshift)
ANSWER_KEY_do_not_use_in_pipeline.csv  - ground-truth fraud labels, validation only
```

## How to run this locally
1. Generate synthetic raw data: `python3 generate_data.py`
2. Clean and transform: `python3 clean_transform.py && python3 build_star_schema.py`
3. Load into the warehouse: `python3 load_warehouse.py`
4. (Optional) Validate the Airflow DAG structure:
   `python3 -c "import sys; sys.path.insert(0,'dags'); import fraud_pipeline_dag"`
5. Connect Power BI (or any BI tool) to `fraud_warehouse.duckdb` for reporting.

## Data quality by design
- All fraud patterns (velocity, geo-mismatch, amount anomaly, odd-hour, new-merchant
  + high value, card-not-present) are deliberately injected into the synthetic data,
  with ground truth kept separate — see `docs/data_dictionary.md`.
- Every cleaning decision (what to fill, what to drop, what to flag as Unknown) is
  documented with its reasoning in `docs/data_dictionary.md` and `architecture_decisions.md`.

## Known limitations (see architecture_decisions.md for full list)
- Quality checks run after load, not before (documented gap, not silent).
- No SCD Type 2 history tracking on dimensions (deliberate scope decision).
- Country-level location granularity only (source data limitation).
