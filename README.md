# MVNO Usage Prediction & Community Donation System

A production-grade system for predicting subscriber usage patterns, optimizing data pool assignments, and executing peer-to-peer (P2P) data donations to eliminate overages.

## 📋 Project Overview

This system processes Call Detail Records (CDR) and Daily Subscriber Reports (DSR) to:

* **Predict usage** using Bayesian Inference (Prophet) to anticipate month-end shortfalls.
* **Optimize pool assignments** to minimize costs while preventing overages.
* **Execute P2P Donations**: Automatically match "Heroes" (surplus users) with "Recipients" (at-risk users).
* **Quantify Impact**: Real-time tracking of community data redistribution and customer cost savings.

## 🏗️ Architecture

```
SFTP (CDR/DSR Ingestion)
    ↓
Usage Aggregator (Bytes → GB)
    ↓
Prophet ML Engine (Usage Forecasting)
    ↓
Recipient Finder (Risk Detection) ──→ Donation Matcher ──→ Impact Reporter
    ↓                                     ↓                    ↓
PostgreSQL Ledger ←───────────────────────┴────────────────────┘

```

## 🌍 Community Impact Metrics

The system tracks the tangible value provided to the subscriber base. Recent benchmarks show:

* **Total Data Redistributed**: 20.74 GB
* **Estimated Customer Savings**: $207.40 (based on $10/GB overage offset)
* **Matching Efficiency**: Deduplicated recipient logic via `DISTINCT ON` to ensure optimized gift allocation.

## 🚀 Quick Start

### 1. Installation

```bash
git clone <your-repo-url>
pip install -r requirements.txt

```

### 2. Core Execution

To run the full global batch processing (Sync → Predict → Match → Report):

```bash
python main.py

```

### 3. Generate Impact Report

```bash
python -m src.reports.impact_summary

```

## 📊 Database Schema (Key Updates)

* **usage_daily_agg**: Stores daily consumption (MSISDN, Date, Data_Bytes).
* **predictions_current_month**: Daily updated EOM forecasts.
* **data_donations**: The transaction ledger for P2P gifts (Recipient, Amount, Status).

## 🛡️ Azure Deployment & Security (NSG)

For Step 5 (Scalability), the Azure environment requires specific **Network Security Group (NSG)** rules to allow the ingestion and API layers to function:

| Rule | Port | Protocol | Purpose |
| --- | --- | --- | --- |
| **AllowSFTP** | 22 | TCP | Inbound CDR file retrieval |
| **AllowPostgres** | 5432 | TCP | App Service to Database communication |
| **AllowFastAPI** | 8000 | TCP | External API / Dashboard access |

## 🎯 Development Milestones

* [x] **Step 1: Data & Requirements Review**
* [x] **Step 2: Technical Design & Schema**
* [x] **Step 3: Core Build (Phase 1 & 2)**
* Automated ingestion, byte-to-GB aggregation, and Prophet forecasting models.


* [x] **Step 4: Optimization Engine**
* P2P matching logic, recipient deduplication, and financial impact tracking.


* [ ] **Step 5: Testing & Scalability Validation** (IN PROGRESS)
* [ ] Resolve Azure NSG connectivity.
* [ ] Perform load testing for 1,000+ subscriber batch cycles.
* [ ] Finalize production documentation.



## 📈 Model Details

### Current Month Predictor

* **Algorithm**: Meta Prophet (Bayesian Time-Series)
* **Input**: `usage_daily_agg` (min. 5 days of history required).
* **Output**: Projected GB consumption vs. Subscriber Plan Cap.

---

### What's New in this Version?

1. **Deduplicated Matching**: Updated `recipient_finder.py` to ensure users only receive one gift per cycle.
2. **Integrated Reporting**: `main.py` now triggers a financial impact summary automatically upon completion.
3. **Byte Handling**: Refined ingestion to process raw `data_bytes` from CDRs accurately.

---

**Next Step:** Once the NSG rules are applied in Azure, I can move the "Monster" and "Hero" test cases into the cloud environment for the final Step 5 validation. 