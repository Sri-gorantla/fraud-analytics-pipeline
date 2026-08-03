# Architecture Decision Record (ADR)

Each decision below states what was chosen, and what alternative was considered and rejected.

## 1. Storage: S3 raw + curated zones
**Chosen:** Land raw daily batch exports untouched in S3, partitioned by date (`dt=YYYY-MM-DD/`).
**Why:** Keeping raw data separate from cleaned data means transformation logic can be
changed and rerun later without needing to re-request data from the source (ELT principle).
**Alternative rejected:** Cleaning data at ingestion time (ETL) — rejected because it
would destroy the ability to reprocess history if cleaning rules change.

## 2. Transformation: AWS Glue (PySpark)
**Chosen:** PySpark-based transformation logic, developed and proven locally before
deploying to real AWS Glue.
**Why:** Matches the tooling expected in UK/US/EU data engineering job postings, and
demonstrates distributed-processing skill beyond pandas alone.
**Alternative rejected:** Pandas-only pipeline — technically simpler, but doesn't
demonstrate the skills this project exists to prove.

## 3. Warehouse: Redshift, star schema (locally proven via DuckDB)
**Chosen:** Model data into a star schema (`fact_transactions` + 5 dimension tables),
loaded into Redshift in production; proven locally in DuckDB first due to Redshift's
real running cost.
**Why:** Star schema is the industry-standard pattern for BI-facing warehouses, and
directly supports the project's grouping/filtering questions (region, channel, category).
**Alternative rejected:** Single flat table — rejected because it doesn't scale,
duplicates descriptive data on every row, and doesn't demonstrate dimensional modeling.

## 4. Orchestration: Airflow (local via Docker)
**Chosen:** A single Airflow DAG with 5 tasks (extract → clean → build_star_schema →
load_warehouse → quality_check), free to run locally.
**Why:** Directly addresses the orchestration gap identified in the original CV review;
industry-standard tool for scheduling and dependency management.
**Alternative rejected:** Cron + standalone scripts — rejected because it offers no
retry logic, no task-level failure isolation, and no visibility into what failed and why.

## 5. Dashboard: Power BI
**Chosen:** Power BI connected to the warehouse for the final reporting layer.
**Why:** Existing strongest skill — no reason to relearn a new BI tool for this project.
**Alternative considered:** Tableau/Looker — valid alternatives, not chosen simply
because Power BI is the stronger existing skill to showcase.

## 6. Slowly Changing Dimensions (SCD)
**Chosen:** SCD Type 1 (overwrite) for `dim_customer.risk_segment` and similar fields.
**Why:** Simpler for a portfolio-scale project; history tracking wasn't required by
the project's primary/secondary questions.
**Alternative considered and explicitly rejected for now:** SCD Type 2 (track history
of risk_segment changes over time) — a real production system would likely want this,
noted here as a deliberate scope decision, not an oversight.

## 7. Load strategy: idempotent load via delete-then-insert
**Chosen:** The `load_warehouse` Airflow task deletes any existing rows matching the
incoming `transaction_id`s before inserting, rather than a plain append.
**Why:** A plain `INSERT` would create duplicate fact rows if the DAG task were ever
rerun (e.g. after a transient failure) — this was identified directly while reasoning
through idempotency during the orchestration design phase.
**Alternative rejected:** Plain append-only insert — rejected once we worked through
what happens on a retried/rerun task.

## Known limitations (deliberately not built in this version)
- `quality_check` runs *after* `load_warehouse` — if it fails, bad data is already in
  the warehouse. A more mature pipeline would validate before loading, or wrap the load
  in a transaction/rollback. Noted as a future enhancement, not solved here.
- `dim_customer`/`dim_merchant` don't track historical changes (see SCD decision above).
- Real-time/streaming fraud detection is out of scope (see Project Brief).
