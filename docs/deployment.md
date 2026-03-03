# Deployment & Operations Guide

**Project:** MVNO Intelligence Hub  
**Client:** Culture Wireless Group  
**Last Updated:** March 3, 2026

---

## Infrastructure

| Component | Details |
|-----------|---------|
| Cloud Provider | Microsoft Azure |
| VM IP | 20.106.102.183 |
| OS | Ubuntu 24.04 LTS |
| User | azurecwg |
| Database | PostgreSQL 10.23 |
| DB Name | mvno_usage_db |
| DB User | postgres |
| Python | 3.10 |
| SFTP Host | cdr.mvnoc.ai:10022 |
| SFTP User | culturewireless |

---

## Initial Setup
```bash
# SSH into server
ssh azurecwg@20.106.102.183

# Navigate to project
cd /home/azurecwg/mvno-intelligence-hub

# Activate virtual environment
source venv/bin/activate

# Verify database
psql -U postgres -d mvno_usage_db -h localhost -c "SELECT COUNT(*) FROM subscribers;"
```

---

## Running the Pipeline

### Manual Run
```bash
cd /home/azurecwg/mvno-intelligence-hub
source venv/bin/activate
python3 main.py
```

### Manual Health Check
```bash
python3 -m src.monitoring.health_check
```

### Manual Load Test
```bash
python3 -m tests.load_test
```

---

## Automated Schedule (Cron)
```
5 0 * * *  python3 main.py >> cron_log.log 2>&1
30 0 * * *  python3 -m src.monitoring.health_check >> logs/health.log 2>&1
```

View current crontab:
```bash
crontab -l
```

---

## Log Files

| Log | Location | Purpose |
|-----|----------|---------|
| Pipeline | `cron_log.log` | Nightly main.py output |
| Health | `logs/health.log` | Nightly health check output |
| Alerts | `logs/health_alerts.log` | Critical failures only |

Check for alerts:
```bash
cat logs/health_alerts.log
tail -50 logs/health.log
tail -50 cron_log.log
```

---

## Database Quick Reference
```bash
# Connect to database
psql -U postgres -d mvno_usage_db -h localhost

# Key table row counts
SELECT COUNT(*) FROM daily_subscriber_reports;
SELECT COUNT(*) FROM daily_usage;
SELECT COUNT(*) FROM usage_daily_agg;
SELECT COUNT(*) FROM predictions_current_month;
SELECT COUNT(*) FROM data_donations;

# Check latest predictions
SELECT msisdn, predicted_data_gb, confidence_upper_gb, current_usage_gb, days_remaining
FROM predictions_current_month
WHERE prediction_date = CURRENT_DATE;

# Check latest donations
SELECT * FROM data_donations
WHERE transaction_date::date = CURRENT_DATE;
```

---

## Common Issues & Fixes

### Pipeline crashes with NoneType error
**Cause:** `predictions_current_month` has stale records with NULL fields  
**Fix:**
```bash
psql -U postgres -d mvno_usage_db -h localhost -c "DELETE FROM predictions_current_month;"
python3 main.py
```

### Donation calculator warning: Insufficient data
**Cause:** `billing_month` format mismatch between tables  
**Fix:** Verify all tables use `YYYY-MM` format:
```bash
psql -U postgres -d mvno_usage_db -h localhost -c "SELECT DISTINCT billing_month FROM pool_assignments;"
psql -U postgres -d mvno_usage_db -h localhost -c "SELECT DISTINCT billing_month FROM predictions_current_month;"
```

### Impact report numbers keep growing
**Cause:** `data_donations` not being deduplicated  
**Fix:** Already resolved — donation_matcher.py checks for existing matches before inserting.

### SFTP connection refused
**Cause:** Azure NSG blocking port 10022 or carrier IP whitelist  
**Fix:** Verify NSG rules allow outbound on port 10022, confirm carrier has whitelisted VM IP.

---

## Updating the Codebase
```bash
cd /home/azurecwg/mvno-intelligence-hub
git pull
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

---

## Architecture Summary
```
cdr.mvnoc.ai:10022 (SFTP)
    ↓
daily_usage + daily_subscriber_reports (PostgreSQL)
    ↓
usage_aggregation.py → usage_daily_agg
    ↓
current_month_predictor.py → predictions_current_month
    ↓
pool_optimizer.py → pool_assignments
donation_calculator.py → donation_thresholds
    ↓
donation_matcher.py → data_donations
    ↓
impact_summary.py → Community Impact Report
    ↓
health_check.py → logs/health_alerts.log
```
