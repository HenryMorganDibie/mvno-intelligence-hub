# MVNO Intelligence Hub - API & Integration Spec

**Project:** MVNO Usage Prediction & Pool Optimization  
**Client:** Culture Wireless Group  
**Last Updated:** March 3, 2026  
**Status:** Production Operational

---

## 1. Data Ingestion

### Sources
Data arrives via SFTP from cdr.mvnoc.ai:10022

| Directory | File Type | Frequency | Status |
|-----------|-----------|-----------|--------|
| `subscriber_report/` | DSR files | Daily | ✅ Active |
| `cdr/` | CDR session files | 15-min intervals | ✅ Active |
| `pr_cdr/` | Roaming CDR files | Daily | ⚠️ All 0 bytes (no roaming activity) |
| `pr_subscriber_report/` | Roaming DSR | Daily | ⚠️ Empty |

### Database Tables (Ingestion Targets)

| Table | Source | Key Fields |
|-------|--------|------------|
| `daily_subscriber_reports` | DSR files | `msisdn`, `usage_date`, `voice_minutes`, `sms_units`, `data_bytes`, `bundle_id` |
| `daily_usage` | CDR files | `msisdn`, `usage_time`, `bytes_up`, `bytes_down` |

---

## 2. Aggregation Layer

Raw data is aggregated nightly into:

**`usage_daily_agg`**
```sql
SELECT
    DATE(usage_time) as usage_date,
    msisdn,
    SUM(bytes_up + bytes_down) as data_bytes,
    COUNT(*) as data_sessions
FROM daily_usage
GROUP BY DATE(usage_time), msisdn
```

**Billing Cycle Convention:**
- Cycle runs 21st to 20th each month
- Stored as `YYYY-MM` format (e.g., `2026-02` = Feb 21 - Mar 20)
- `get_current_billing_cycle_dates()` in `usage_aggregation.py` handles all date logic

---

## 3. Prediction Engine

**Model:** Meta Prophet (Bayesian Time-Series)  
**Module:** `src/models/current_month_predictor.py`

### Input
- Reads from `daily_usage` via `usage_daily_agg`
- Minimum 2 days of history required
- Training window: 90 days lookback

### Output — `predictions_current_month`

| Field | Type | Description |
|-------|------|-------------|
| `msisdn` | varchar | Subscriber phone number |
| `billing_month` | varchar | Billing cycle (YYYY-MM) |
| `prediction_date` | date | Date prediction was generated |
| `predicted_data_gb` | numeric | Projected total GB by month-end |
| `confidence_lower_gb` | numeric | 90% confidence lower bound |
| `confidence_upper_gb` | numeric | 90% confidence upper bound |
| `days_remaining` | int | Days left in billing cycle |
| `current_usage_gb` | numeric | Actual usage to date |
| `model_version` | varchar | `prophet_v1` |

### Prediction Workflow
```
daily_usage
    → populate_daily_aggregates() → usage_daily_agg
    → prepare_training_data() → Prophet DataFrame (ds, y)
    → model.fit() → model.predict()
    → save_prediction_to_db() → predictions_current_month
```

---

## 4. Pool Optimization

**Module:** `src/optimization/pool_optimizer.py`

### Pool Tiers

| tier_id | tier_name | data_cap_gb |
|---------|-----------|-------------|
| 1 | Basic | 5 GB |
| 101 | Small Hero | 10 GB |
| 100 | Big Hero | 100 GB |

### Assignment Logic
1. Fetch predicted usage for subscriber
2. Add 10% safety buffer
3. Assign cheapest tier that covers buffered prediction
4. Write to `pool_assignments` with billing_month

---

## 5. Donation Engine

**Modules:** `src/optimization/donation_calculator.py`, `src/optimization/donation_matcher.py`

### Safe Donation Formula
```
uncertainty_gb = confidence_upper_gb - predicted_data_gb
confidence_buffer_gb = uncertainty_gb * 1.2
safe_donation_gb = data_cap_gb - predicted_data_gb - confidence_buffer_gb
```

### Matching Logic
- `recipient_finder.py` — finds at-risk subscribers (predicted > cap)
- `donation_matcher.py` — round-robin allocation from donor pool
- Max gift per match: 2.0 GB
- Duplicate prevention: one donor→recipient match per day
- Results written to `data_donations`

### `data_donations` Schema

| Field | Type | Description |
|-------|------|-------------|
| `donor_msisdn` | varchar | Donor phone number |
| `recipient_msisdn` | varchar | Recipient phone number |
| `amount_gb` | numeric | GB transferred |
| `transaction_date` | timestamp | When match occurred |
| `status` | varchar | `COMPLETED` |

---

## 6. Monitoring

**Module:** `src/monitoring/health_check.py`

### Health Checks (7 Points)

| Check | What It Validates | Alert Condition |
|-------|------------------|-----------------|
| Database Connectivity | DB is reachable | Connection failure |
| SFTP Ingestion | New DSR data in last 48h | No records in 48h |
| Usage Aggregation | Aggregation ran in last 24h | No updates in 24h |
| Predictions Fresh | Predictions generated today | 0 predictions today |
| Predictions Complete | All fields populated | Any NULL fields |
| Donation Matching | Matching cycle ran | Logged only |
| Subscriber Count | Table not empty | 0 subscribers |

### Alert Logs
- `logs/health.log` — full health check output
- `logs/health_alerts.log` — critical alerts only
- `logs/cron_log.log` — nightly pipeline output

---

## 7. Automated Schedule

| Time | Command | Purpose |
|------|---------|---------|
| 12:05 AM | `python3 main.py` | Full pipeline run |
| 12:30 AM | `python3 -m src.monitoring.health_check` | System validation |

---

## 8. Performance Benchmarks (Load Test — March 3, 2026)

| Metric | Result |
|--------|--------|
| Total subscribers tested | 30,000 |
| Usage records processed | 5,389,383 |
| Aggregation throughput | 1,480 subscribers/sec |
| Prediction success rate | 100% (100/100 sample) |
| DB lookup speed | 2-5ms |
| Projected 30K prediction time | ~4.4 hours (sequential) |

**Optimization Note:** Prediction time can be reduced significantly by skipping retrain for subscribers whose data hasn't changed since last run. Recommended for production at scale.

---

## 9. Known Limitations & Next Steps

| Item | Status | Notes |
|------|--------|-------|
| Voice/SMS data | Not yet populated | DSR files have NULL voice_minutes and sms_units |
| Bundle/plan data | Not yet populated | bundle_id NULL for all subscribers |
| Roaming CDRs | No activity | All pr_cdr files are 0 bytes |
| Parallel predictions | Not implemented | Sequential Prophet training limits throughput |
| Subscriber plan tiers | Hardcoded | Needs real plan data from carrier |
