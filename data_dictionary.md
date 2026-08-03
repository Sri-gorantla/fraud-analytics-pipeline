# Data Dictionary

## fact_transactions (13,392 rows — grain: one row = one transaction)
| Column | Type | Description | Notes |
|---|---|---|---|
| transaction_id | VARCHAR (PK) | Unique transaction identifier | |
| customer_id | VARCHAR (FK) | References `dim_customer.customer_id` | |
| merchant_id | VARCHAR (FK) | References `dim_merchant.merchant_id` | |
| location_id | VARCHAR (FK) | References `dim_location.location_id` | |
| channel_id | VARCHAR (FK) | References `dim_channel.channel_id` | |
| date_id | VARCHAR (FK) | References `dim_date.date_id` | |
| transaction_time | VARCHAR | Precise time of day (HH:MM:SS) | Deliberately NOT its own dimension — too high cardinality to be a useful grouping dimension |
| amount | DECIMAL(12,2) | Transaction amount | Cleaned: negative values corrected (sign errors), 50x+ customer-median outliers treated as entry errors and corrected, missing values (~2%, confirmed MCAR) filled with median |

## dim_customer (800 rows)
| Column | Type | Description |
|---|---|---|
| customer_id | VARCHAR (PK) | Unique customer identifier |
| account_type | VARCHAR | Current / Savings / Premium |
| home_country | VARCHAR | Customer's registered home country |
| tenure_months | INTEGER | Months since account opened |
| risk_segment | VARCHAR | Low / Medium / High |

## dim_merchant (150 rows)
| Column | Type | Description |
|---|---|---|
| merchant_id | VARCHAR (PK) | Unique merchant identifier |
| category | VARCHAR | Merchant category (Groceries, Electronics, Travel, etc.) — recovered via mode-per-merchant lookup where raw category was missing |
| risk_tier | VARCHAR | Low / Medium / High |
| country | VARCHAR | Merchant's operating country |

## dim_location (6 rows)
| Column | Type | Description |
|---|---|---|
| location_id | VARCHAR (PK) | Unique location identifier |
| country | VARCHAR | Country of the transaction. **Note:** grain is country-level only — the source data doesn't capture city/region, so this dimension is simpler than originally scoped in early design; noted as a known limitation, not an oversight. |

## dim_channel (3 rows)
| Column | Type | Description |
|---|---|---|
| channel_id | VARCHAR (PK) | Unique channel identifier |
| channel_type | VARCHAR | Online / POS / ATM |

## dim_date (60 rows)
| Column | Type | Description |
|---|---|---|
| date_id | VARCHAR (PK) | YYYYMMDD format |
| full_date | DATE | Calendar date |
| month | INTEGER | 1-12 |
| quarter | INTEGER | 1-4 |
| day_of_week | VARCHAR | Monday-Sunday |
| is_weekend | BOOLEAN | True for Saturday/Sunday |

## Fields intentionally excluded from the raw/fact data
| Field | Why it's not here |
|---|---|
| is_fraud (ground truth) | A real bank export would not have this at ingestion time — fraud is confirmed later via chargebacks/investigation, not known at the moment of the transaction. Kept in a separate `ANSWER_KEY` file, used only to validate detection logic after the fact, never fed into the pipeline itself. |
| risk_score | Not yet computed — planned for the analysis phase (Part 11), derived from the fraud pattern features (velocity, geo-mismatch, amount anomaly, odd-hour, new-merchant, CNP) rather than stored as a raw field. |

## Known data quality decisions made during cleaning
- **Casing/whitespace standardization** applied to all categorical fields (channel, category, country, account_type, risk fields) — raw data had up to 10 spelling variants for 3 real values in some columns.
- **Country acronym fix** — `.title()` case-standardization broke `USA`/`UK` into `Usa`/`Uk`; corrected via an explicit mapping applied after title-casing.
- **Missing `transaction_country`** (668 rows) — recovered via merchant lookup (merchant's country is fixed, so looked up from other rows sharing the same `merchant_id`), not guessed or dropped.
- **Missing `merchant_category`** — not reliably recoverable the same way initially; ultimately recovered via mode-per-merchant lookup once duplicate/inconsistent values were resolved.
- **Missing `customer_tenure_months`** — recovered via customer_id lookup (fixed per customer).
- **Duplicates** — defined uniqueness by `transaction_id` specifically (not "whole row identical"), removed via `drop_duplicates(subset=['transaction_id'])`.
