# Analysis Findings — Fraud & Risk Detection

## Method
Six fraud signals were computed directly from the warehouse (`fact_transactions` +
dimensions) — **without** ever referencing the ground-truth answer key during signal
design. The answer key was used only once, at the end, purely to grade performance.
This mirrors how a real fraud model would be built: designed from domain reasoning
(Part 2 of the playbook), then validated against known outcomes.

### Signals computed
| Signal | Definition used |
|---|---|
| Geo-mismatch | Country changed from the customer's immediately preceding transaction, within a 3-hour window (implausible travel time) |
| Amount anomaly | Transaction amount > 5x this customer's own median spend |
| Odd-hour | Transaction between midnight and 5am |
| Velocity | 4+ transactions by the same customer within a rolling 60-minute window |
| New merchant + high value | First-ever transaction with this merchant, and amount > 3x customer's median |
| CNP (card-not-present) | Channel = Online |

`risk_score` = count of signals triggered simultaneously (0-6).

## Note on a bug caught and fixed during this analysis
The first version of the geo-mismatch signal simply compared "transaction country"
vs. "customer's home country" — this fired on **82.73%** of all transactions, because
the synthetic data generator assigns merchant country randomly regardless of customer
home country, meaning most *normal* transactions already look "foreign." This isn't a
useful fraud signal — a signal firing on 83% of everything discriminates nothing.

**Fix:** redefined geo-mismatch to require a country change between two of the *same
customer's own consecutive transactions*, within a 3-hour window — i.e., genuinely
implausible travel, not just "shopped at a foreign merchant." This dropped the trigger
rate to a plausible **4.51%**.

## Threshold analysis (detection rate vs. false positive rate)
| Threshold (signals triggered) | Transactions flagged | Detection rate | False positive rate |
|---|---|---|---|
| ≥1 | 6,395 | 97.8% | 46.89% |
| **≥2** | **441** | **85.5%** | **1.87%** |
| ≥3 | 135 | 57.0% | 0.04% |
| ≥4 | 33 | 14.5% | 0.00% |

**Chosen threshold: ≥2 signals.** Catches 85.5% of real fraud while wrongly flagging
only 1.87% of genuine customers — a defensible business tradeoff. Threshold ≥1 catches
slightly more fraud (97.8%) but at the cost of flagging nearly half of all genuine
transactions, which would be operationally unworkable (this is the "flag everything"
trap discussed in Part 2.3 of the playbook, just less extreme).

## Detection rate by fraud type (at threshold ≥2)
| Fraud type | Caught | Total | Detection rate |
|---|---|---|---|
| Amount anomaly | 20 | 20 | 100% |
| New merchant + high value | 14 | 14 | 100% |
| Odd-hour | 15 | 15 | 100% |
| Velocity | 142 | 164 | 86.6% |
| Geo-mismatch | 4 | 15 | **26.7%** |

**Known limitation, reported honestly:** geo-mismatch detection is weak. This is
partly because the injected geo-mismatch fraud pattern in the synthetic data doesn't
itself enforce rapid succession between transactions (it places one foreign
transaction at a random time in the day) — so the *injected pattern* and the
*detection definition* aren't fully aligned. A production version would need to
either redesign the injected pattern to better reflect true "impossible travel"
fraud, or use a softer geo-based signal (e.g., distance from customer's most common
transaction country over a longer window) rather than strict consecutive-transaction
proximity.

## Secondary questions answered

**Which channels carry the highest fraud exposure?**
| Channel | Fraud rate |
|---|---|
| Online | 3.48% |
| POS | 0.25% |
| ATM | 0.00% |

Online carries roughly **14x** the fraud rate of POS — directly validating the
card-not-present (CNP) fraud concept from Part 2.2 with real numbers.

**Which merchant categories carry the highest fraud exposure?**
| Category | Fraud rate |
|---|---|
| Electronics | 2.76% |
| Dining | 1.68% |
| Entertainment | 1.68% |
| Online Retail | 1.63% |
| Travel | 1.62% |
| Fashion | 1.44% |
| Groceries | 1.41% |
| Fuel | 1.29% |

Electronics carries roughly double the fraud rate of the lowest category (Fuel) —
an actionable finding for prioritizing manual review resources.

## Answer to the project's primary question
*"Which transaction patterns most reliably indicate fraud risk, and what does a rule
based on them catch vs. miss?"*

A rule flagging transactions with 2 or more simultaneous risk signals catches 85.5%
of fraud at a 1.87% false-positive cost, driven mainly by amount anomalies, odd-hour
activity, new-merchant spikes, and transaction velocity. Geo-mismatch, as currently
defined, is the weakest-performing signal and is documented as a known limitation
rather than hidden — a realistic outcome, since real fraud modeling rarely produces
uniformly strong signals across every pattern on a first pass.
