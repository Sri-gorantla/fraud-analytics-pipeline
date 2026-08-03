# Project Brief: Fraud & Risk Analytics Pipeline

## Business context (simulated)
A mid-sized retail bank processes tens of thousands of card transactions daily
across online, POS, and ATM channels. Currently, fraud review happens reactively —
customer complaints or chargebacks trigger investigation, but there's no systematic
way to spot risk patterns before losses occur. The risk team wants a repeatable
pipeline that surfaces fraud-pattern signals from transaction data on a regular basis,
instead of ad-hoc manual review.

## Primary question this project answers
Which transaction patterns most reliably indicate fraud risk, and how well would
a rule built on those patterns actually perform — what does it catch, what does it miss?

## Secondary questions
- Which merchant categories and channels (online/POS/ATM) carry the highest fraud rate?
- Does fraud risk cluster around specific times, locations, or transaction sizes?
- What's the rough tradeoff between catching more fraud vs. flagging too many genuine
  customers (false positives)?

## Out of scope (deliberately)
- This project builds the data pipeline and analysis only — no ML model deployment.
- Uses synthetic data only — no real customer/transaction data.
- Real-time/streaming detection — batch pipeline only, for this version.

## Success criteria
- Pipeline runs end-to-end (S3 raw zone → clean/transform → warehouse) on a schedule
  without manual intervention.
- Built-in data quality checks catch bad/missing/invalid data automatically.
- Dashboard answers the primary + secondary questions clearly enough that a
  non-technical stakeholder (e.g. a risk manager) could act on it.

## Grain
One row in `fact_transactions` = one transaction.
