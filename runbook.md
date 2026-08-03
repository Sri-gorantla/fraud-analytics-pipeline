# Runbook — What To Check If the Pipeline Fails

DAG: `fraud_analytics_daily_pipeline` (5 tasks, run daily)

## Task: extract_daily_file
**Fails when:** the raw file for today's date doesn't exist yet in `s3_raw_zone/transactions/dt=YYYY-MM-DD/`.
**Check first:** has the upstream source (in production: the bank's export system)
actually delivered today's file? This is an *upstream* problem, not a bug in our pipeline.
**Do NOT:** manually create a placeholder file to make the task pass — this would
silently hide a real missing-data day.

## Task: clean_data
**Fails when:** an unexpected value breaks a parsing step (e.g. a date format we
haven't seen before, or a genuinely new category we didn't anticipate).
**Check first:** re-run the profiling step (same as Part 1/7) manually against today's
raw file to see what's actually different about it compared to previous days.
**Safe to rerun:** yes — this task fully overwrites its output, no side effects from reruns.

## Task: build_star_schema
**Fails when:** a referential integrity issue exists that cleaning didn't catch — e.g.
a transaction referencing a customer_id or merchant_id never seen before.
**Check first:** query the cleaned flat file for IDs that don't appear in the existing
dimension tables. In production, this might mean a genuinely new customer/merchant needs
to be added to the dimension tables first (a real "new dimension member" scenario).
**Safe to rerun:** yes — fully overwrites its output.

## Task: load_warehouse
**Fails when:** a database connection issue, or a constraint violation (e.g. a
transaction_id collision that shouldn't be possible given upstream deduplication).
**Check first:** confirm `build_star_schema` actually completed successfully and
produced a valid `fact_transactions.csv` before this task ran.
**Safe to rerun:** YES, by design — this task deletes matching transaction_ids before
inserting, specifically so reruns never create duplicates. This was a deliberate
design decision (see architecture_decisions.md, #7).

## Task: quality_check
**Fails when:** the assertions catch something real — negative amounts, missing
customer_ids, or row counts far outside the expected daily range.
**Check first:** this is your last line of defense — if it fails, treat it seriously.
Don't just "fix the assertion" to make it pass; investigate why the data violated
the assumption in the first place.
**Known limitation:** this task runs *after* the load, so if it fails, bad data is
already in the warehouse. Manual remediation (or a rollback) would currently be
needed — this is a documented gap, not a silent one (see architecture_decisions.md).
**Safe to rerun:** yes, this task is fully read-only.

## General principle for any failure
Per the playbook's Part 9 discipline: because tasks are separated and idempotent
where it matters (especially `load_warehouse`), you should almost never need to
rerun the entire DAG from scratch — only the specific failed task and everything
downstream of it.
