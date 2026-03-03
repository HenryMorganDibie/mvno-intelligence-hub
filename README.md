# MVNO Usage Prediction & Community Donation System

A production-grade system for predicting subscriber usage patterns, optimizing data pool assignments, and executing peer-to-peer (P2P) data donations to eliminate overages.

## 📋 Project Overview

This system processes Daily Subscriber Reports (DSR) and Call Detail Records (CDR) delivered via SFTP to:

* **Predict usage** using Bayesian Inference (Prophet) to anticipate month-end shortfalls.
* **Optimize pool assignments** to minimize costs while preventing overages.
* **Execute P2P Donations**: Automatically match "Heroes" (surplus users) with "Recipients" (at-risk users).
* **Quantify Impact**: Real-time tracking of community data redistribution and customer cost savings.

## 🏗️ Architecture
```
SFTP (DSR/CDR Ingestion)
    ↓
daily_usage + daily_subscriber_reports (PostgreSQL)
    ↓
Usage Aggregator (Bytes → GB → usage_daily_agg)
    ↓
Prophet ML Engine (Usage Forecasting)
    ↓
Recipient Finder (Risk Detection) ──→ Donation Matcher ──→ Impact Reporter
    ↓                                     ↓                    ↓
PostgreSQL Ledger ←───────────────────────┴────────────────────┘
```

## 🌍 Community Impact Metrics

* **Prediction Accuracy:** 100/100 subscribers successfully predicted at load test scale
* **Donation Matching:** Duplicate-safe, round-robin allocation with daily deduplication
* **Overage Prevention:** At-risk subscribers automatically matched with donors each cycle
* **Estimated Savings:** $10/GB overage offset tracked per billing cycle

## 🚀 Quick Start

### 1. Installation
```bash
git clone <your-repo-url>
cd mvno-intelligence-hub
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Database Setup
```bash
sudo systemctl start postgresql
psql -U postgres -d mvno_usage_db -h localhost
```

### 3. Run the Pipeline
```bash
python3 main.py
```

### 4. Run Health Check
```bash
python3 -m src.monitoring.health_check
```

### 5. Run Load Test
```bash
python3 -m tests.load_test
```

## 📊 Database Schema (Key Tables)

| Table | Purpose |
|-------|---------|
| `daily_usage` | Raw CDR session data (bytes_up, bytes_down per session) |
| `daily_subscriber_reports` | Daily DSR snapshots from SFTP (voice, sms, data_bytes) |
| `usage_daily_agg` | Aggregated daily totals per subscriber |
| `predictions_current_month` | Prophet model forecasts with confidence intervals |
| `pool_assignments` | Subscriber tier assignments per billing cycle |
| `donation_thresholds` | Safe donation amounts per subscriber |
| `data_donations` | Transaction ledger for all P2P data gifts |

## ⚙️ Automated Schedule (Cron)

| Time | Job | Purpose |
|------|-----|---------|
| Every 15 mins | `sftp_puller.py` | Pulls new CDR/DSR files from carrier SFTP and ingests them |
| 12:05 AM | `main.py` | Full pipeline: aggregate → predict → match → report |
| 12:30 AM | `health_check.py` | 7-point system validation, alerts to `logs/health.log` |

## 📈 Load Test Results (March 3, 2026)

Validated at 30,000 subscriber scale with 90 days of history:

| Metric | Result |
|--------|--------|
| Subscribers seeded | 30,000 |
| Usage records generated | 5,389,383 |
| Subscriber seeding | 4.98s |
| Aggregation throughput | 1,480 subscribers/sec |
| Prediction success rate | 100/100 (100%) |
| DB query speed (lookups) | 2-5ms |

## 🛡️ Monitoring

The health check validates 7 system components on every run:

1. Database connectivity
2. SFTP ingestion freshness (last 48h)
3. Usage aggregation currency
4. Predictions generated today
5. Prediction field completeness
6. Donation matching execution
7. Subscriber count integrity

Alerts are written to `logs/health_alerts.log` and logged at CRITICAL level.

## 🛡️ Azure Deployment

| Rule | Port | Protocol | Purpose |
|------|------|----------|---------|
| AllowSFTP | 10022 | TCP | Inbound DSR/CDR file retrieval from cdr.mvnoc.ai |
| AllowPostgres | 5432 | TCP | App to database communication |
| AllowSSH | 22 | TCP | Management access |

## 🎯 Development Milestones

* [x] **Step 1: Data & Requirements Review** — CDR/DSR formats confirmed, billing cycle 21st-20th
* [x] **Step 2: Technical Design** — Schema, architecture, and data flow documented
* [x] **Step 3: Core Build** — SFTP ingestion, DSR/CDR parsing, usage aggregation, Prophet forecasting
* [x] **Step 4: Optimization Engine** — Pool assignment, donation calculator, P2P matching, impact reporting
* [x] **Step 5: Testing & Scalability Validation** — Load tested at 30K subscribers (5.3M records), monitoring setup, cron automation, full documentation

## 📁 Project Structure
```
mvno-intelligence-hub/
├── main.py                          # Pipeline orchestrator
├── config/
│   ├── database.py                  # DB connection and pooling
│   └── logging_config.py            # Centralized logging
├── src/
│   ├── features/
│   │   └── usage_aggregation.py     # Byte → GB aggregation
│   ├── models/
│   │   └── current_month_predictor.py  # Prophet forecasting
│   ├── optimization/
│   │   ├── pool_optimizer.py        # Tier assignment logic
│   │   ├── donation_calculator.py   # Safe donation amounts
│   │   ├── donation_matcher.py      # Round-robin P2P matching
│   │   └── recipient_finder.py      # At-risk subscriber detection
│   ├── reports/
│   │   └── impact_summary.py        # Community impact report
│   └── monitoring/
│       └── health_check.py          # 7-point system health monitor
├── tests/
│   └── load_test.py                 # 30K subscriber load test
├── docs/
│   ├── architecture.md              # System architecture
│   └── deployment.md               # Deployment and ops guide
└── logs/
    ├── health.log                   # Nightly health check output
    ├── health_alerts.log            # Critical alerts only
    └── cron_log.log                 # Pipeline execution log
```

## 📈 Model Details

### Current Month Predictor

* **Algorithm:** Meta Prophet (Bayesian Time-Series)
* **Input:** `daily_usage` table aggregated into `usage_daily_agg`
* **Training Window:** 90 days of history
* **Output:** Projected GB by month-end with 90% confidence intervals
* **Minimum Data:** 2 days required to train

### Pool Optimization

* **Tiers:** Basic (5GB), Small Hero (10GB), Big Hero (100GB)
* **Logic:** Assign cheapest tier that covers predicted usage + 10% safety buffer
* **Billing Convention:** Cycle runs 21st to 20th, stored as `YYYY-MM` format

---

**System Status:** ✅ Production Operational  
**Last Updated:** March 3, 2026  
**Maintained by:** Henry Dibie
