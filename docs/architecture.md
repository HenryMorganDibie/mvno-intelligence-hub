# MVNO Usage Prediction System - Technical Design Document

**Project:** MVNO Usage Prediction & Pool Optimization  
**Client:** Culture Wireless Group  
**Date:** January 30, 2026  
**Version:** 1.0  

---

## 1. Executive Summary

This document outlines the technical architecture, data flow, and implementation strategy for the MVNO Usage Prediction and Pool Optimization System. The system will process Call Detail Records (CDR) and Daily Subscriber Reports (DSR) to predict subscriber usage, optimize pool tier assignments, and calculate safe data donation thresholds.

**Key Deliverables:**
- Real-time, current month, and next month usage predictions
- Automated pool tier optimization
- Data donation threshold calculations
- REST API for user profile integration

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SFTP Server (Every 15 mins)                 │
│                  CDR Files (Voice/SMS/Data) + DSR Files         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Ingestion Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ SFTP Client  │  │  CDR Parser  │  │  DSR Parser  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PostgreSQL + TimescaleDB                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   CDR Tables │  │  DSR Tables  │  │  Aggregates  │         │
│  │ (Hypertables)│  │ (Hypertables)│  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Feature Engineering Layer                      │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Usage Aggregation | Velocity Calculation        │          │
│  │  Pattern Detection | Seasonal Features           │          │
│  └──────────────────────────────────────────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ML Prediction Models                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Real-Time  │  │ Current Month│  │  Next Month  │         │
│  │   Predictor  │  │  Predictor   │  │  Predictor   │         │
│  │  (Prophet)   │  │  (Ensemble)  │  │  (Prophet)   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└──────────┬──────────────────┬──────────────────┬────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Optimization & Business Logic                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │Pool Optimizer│  │   Donation   │  │     Cost     │         │
│  │              │  │  Calculator  │  │  Minimizer   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │Usage Endpoint│  │   Prediction │  │   Donation   │         │
│  │              │  │   Endpoints  │  │   Endpoints  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   User Profile Dashboard                        │
│              (Culture Wireless App/Website)                     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Database** | PostgreSQL 14+ with TimescaleDB | Time-series optimization, excellent for CDR data, automatic partitioning |
| **Backend** | Python 3.9+ | Rich ML ecosystem, rapid development |
| **API Framework** | FastAPI | High performance, automatic documentation, async support |
| **ML Libraries** | Prophet, XGBoost, scikit-learn | Proven time-series forecasting, ensemble capabilities |
| **Data Processing** | Pandas, NumPy | Industry standard for data manipulation |
| **File Transfer** | Paramiko (SFTP) | Secure file transfer, Python-native |
| **Deployment** | Azure Functions + Container Apps | Serverless scheduling, scalable API hosting |

---

## 3. Database Design

### 3.1 Schema Overview

**Core Tables:**
- `subscribers` - Master subscriber information
- `daily_subscriber_reports` - DSR snapshots (TimescaleDB hypertable, 7-day chunks)
- `cdr_voice`, `cdr_sms`, `cdr_data` - Call detail records (TimescaleDB hypertables, 1-day chunks)

**Aggregation Tables:**
- `usage_daily_agg` - Pre-aggregated daily usage per subscriber
- `usage_monthly_agg` - Running monthly totals (automatically updated via trigger)

**Prediction Tables:**
- `predictions_realtime` - 15-min to 1-hour forecasts
- `predictions_current_month` - End-of-month predictions (updated daily)
- `predictions_next_month` - Next billing cycle predictions

**Optimization Tables:**
- `pool_tiers` - Tier definitions (caps, costs)
- `pool_assignments` - Historical tier assignments
- `pool_optimization_log` - Daily optimization results

**Donation Tables:**
- `donation_thresholds` - Safe donation amounts (updated daily)
- `donations` - Actual donation transactions

### 3.2 Data Flow

```
Raw CDR/DSR Files → Raw Tables (Hypertables) → Daily Aggregates → Monthly Aggregates
                                                       ↓
                                                 ML Features → Predictions → Optimization
```

### 3.3 Indexing Strategy

**Primary Indexes:**
- `msisdn` on all subscriber-related tables (user lookups)
- `usage_date` / `effective_date` on time-series tables (range queries)
- `bundle_id`, `tier_id` for pool-related queries

**Composite Indexes:**
- `(usage_date, msisdn)` for efficient time-series + subscriber queries
- `(billing_month, msisdn)` for monthly aggregations

### 3.4 Data Retention

- **Raw CDR/DSR data:** 90 days (after that, keep only aggregates)
- **Daily aggregates:** 2 years
- **Monthly aggregates:** Indefinite
- **Predictions:** 60 days (historical tracking)

---

## 4. ML Model Architecture

### 4.1 Real-Time Usage Predictor

**Purpose:** Predict usage in next 15-60 minutes to prevent immediate overages

**Algorithm:** Facebook Prophet
- Handles missing data gracefully
- Captures intra-day patterns
- Fast inference (<100ms per subscriber)

**Features:**
- Recent usage velocity (last 1 hour, 3 hours, 6 hours)
- Time of day
- Day of week
- Current session duration

**Update Frequency:** Every 15 minutes (with new CDR data)

**Output:**
- Predicted data usage (MB) for next 15, 30, 60 minutes
- 90% confidence interval

### 4.2 Current Month Predictor

**Purpose:** Predict total usage by end of current billing cycle

**Algorithm:** Ensemble (Prophet 60% + XGBoost 40%)
- Prophet captures seasonality and trends
- XGBoost learns non-linear patterns and subscriber-specific behaviors

**Features:**
- Month-to-date usage (voice, SMS, data)
- Historical monthly usage (last 3 months)
- Day of month
- Days remaining in cycle
- Subscriber characteristics (bundle_id, activation_date)
- Usage velocity (daily average, weekly trend)

**Update Frequency:** Daily at 1 AM

**Output:**
- Predicted total data usage (GB) by month-end
- 90% confidence interval
- Probability of exceeding current tier cap

### 4.3 Next Month Predictor

**Purpose:** Predict usage for next billing cycle (for donation threshold planning)

**Algorithm:** Prophet with yearly seasonality
- Captures month-to-month patterns
- Accounts for subscriber growth/decline trends

**Features:**
- Historical monthly usage (last 6 months)
- Trend direction
- Seasonal components
- Subscriber tenure

**Update Frequency:** Daily at 1 AM

**Output:**
- Predicted data usage (GB) for next month
- 80% confidence interval (wider for longer horizon)

### 4.4 Model Validation Strategy

**Backtesting:**
- Rolling window validation (30-day train, 7-day test)
- Walk-forward validation to prevent data leakage

**Metrics:**
- RMSE (Root Mean Squared Error) - primary metric
- MAE (Mean Absolute Error)
- MAPE (Mean Absolute Percentage Error)
- Coverage (% of actuals within confidence interval)

**Acceptance Criteria:**
- MAPE < 15% for current month predictions
- MAPE < 20% for next month predictions
- 90% coverage for confidence intervals

**Monitoring:**
- Track prediction error trends in `model_metrics` table
- Alert if MAPE exceeds thresholds for 3 consecutive days
- Retrain models monthly with updated data

---

## 5. Pool Optimization Logic

### 5.1 Objective Function

**Goal:** Minimize total cost while ensuring no subscriber exceeds their tier cap

```
Minimize: Σ(tier_cost[i] × num_subscribers[i])

Subject to:
- predicted_usage[subscriber] ≤ tier_cap[assigned_tier] × (1 - safety_buffer)
- safety_buffer = 10% (configurable)
```

### 5.2 Assignment Algorithm

**Daily Optimization Process:**

1. **For each subscriber:**
   - Get current month prediction + confidence interval upper bound
   - Calculate required capacity = predicted_usage + (confidence_upper - predicted_usage) × safety_factor
   
2. **Tier Selection:**
   - Assign to lowest-cost tier where: `tier_cap ≥ required_capacity`
   - If no tier fits, assign to highest tier + flag for manual review

3. **Stability Rules:**
   - Don't move subscriber if new tier cost difference < $2
   - Max 1 tier move per subscriber per month
   - Lock tier assignments 7 days before billing cycle end

4. **Batch Optimization:**
   - Re-run optimization daily
   - Track cost savings vs. no-optimization baseline
   - Log all tier changes with reason codes

### 5.3 Cost Calculation

**Monthly Cost:**
```
Total Cost = Σ(subscribers_in_tier[i] × tier_cost[i]) + overage_charges
```

**Overage Charges:**
- If subscriber exceeds tier cap: `overage_gb × overage_cost_per_gb`
- Track in `pool_optimization_log` table

---

## 6. Donation Threshold Calculation

### 6.1 Safe Donation Logic

**Formula:**
```
Safe Donation Amount = Allocated Capacity - Predicted Usage - Confidence Buffer

Where:
- Allocated Capacity = tier_cap for subscriber's current tier
- Predicted Usage = current_month_prediction
- Confidence Buffer = (confidence_upper - predicted_usage) × safety_factor
- safety_factor = 1.2 (20% buffer to prevent overages)
```

**Example:**
```
Subscriber A:
- Current Tier: 10 GB
- Predicted Usage: 6.5 GB
- Confidence Upper: 7.3 GB
- Confidence Buffer: (7.3 - 6.5) × 1.2 = 0.96 GB
- Safe Donation: 10 - 6.5 - 0.96 = 2.54 GB

Display to user: "You can safely donate up to 2.5 GB this month"
```

### 6.2 Real-Time Updates

**Update Frequency:** Daily (or when usage crosses thresholds)

**Threshold Alerts:**
- When safe donation drops below 1 GB → Update app UI
- When safe donation reaches 0 → Disable donation option
- When subscriber receives donation → Recalculate their safe amount

### 6.3 Donation Mechanics

**Business Rules:**
1. Donations are cumulative per month
2. Donors earn reward points (1 point per GB donated)
3. Recipients are prioritized by need (closest to overage)
4. Donations are non-refundable within billing cycle

---

## 7. API Design

### 7.1 Endpoint Specifications

#### **GET /api/usage/{msisdn}**
Returns current month usage summary

**Response:**
```json
{
  "msisdn": "2025551234",
  "billing_month": "2026-01",
  "usage": {
    "voice_minutes": 145.5,
    "sms_count": 287,
    "data_gb": 6.34
  },
  "tier": {
    "tier_id": 2,
    "tier_name": "Tier 2 - Standard",
    "data_cap_gb": 10.0
  },
  "days_remaining": 18,
  "last_updated": "2026-01-30T10:15:00Z"
}
```

#### **GET /api/predictions/{msisdn}/current-month**
Returns end-of-month prediction

**Response:**
```json
{
  "msisdn": "2025551234",
  "billing_month": "2026-01",
  "prediction": {
    "data_gb": 8.7,
    "confidence_lower": 7.9,
    "confidence_upper": 9.5
  },
  "risk_level": "low",
  "will_exceed_tier": false,
  "predicted_at": "2026-01-30T01:00:00Z"
}
```

#### **GET /api/donations/{msisdn}/threshold**
Returns safe donation amount

**Response:**
```json
{
  "msisdn": "2025551234",
  "safe_donation_gb": 2.54,
  "allocated_capacity_gb": 10.0,
  "predicted_usage_gb": 6.5,
  "confidence_buffer_gb": 0.96,
  "calculated_at": "2026-01-30T01:00:00Z",
  "can_donate": true
}
```

#### **POST /api/donations**
Records a data donation

**Request:**
```json
{
  "donor_msisdn": "2025551234",
  "amount_gb": 2.0,
  "recipient_msisdn": "2025555678"
}
```

**Response:**
```json
{
  "donation_id": 12345,
  "status": "completed",
  "reward_points": 2,
  "new_safe_donation_gb": 0.54
}
```

### 7.2 Authentication & Rate Limiting

**Authentication:** API key-based (for Culture Wireless App)
- Each request includes `X-API-Key` header
- Keys stored in `api_keys` table with rate limits

**Rate Limiting:**
- 100 requests/minute per subscriber
- 1000 requests/minute per API key
- Burst allowance: 150 requests/10 seconds

---

## 8. Scheduled Jobs

### 8.1 Job Schedule

| Job Name | Frequency | Time (EST) | Purpose |
|----------|-----------|------------|---------|
| **CDR/DSR Ingestion** | Every 15 mins | Continuous | Pull new files from SFTP |
| **Daily Aggregation** | Daily | 12:30 AM | Update daily usage aggregates |
| **Current Month Predictions** | Daily | 1:00 AM | Update all subscriber predictions |
| **Next Month Predictions** | Daily | 1:30 AM | Update next month forecasts |
| **Pool Optimization** | Daily | 2:00 AM | Recalculate optimal tier assignments |
| **Donation Threshold Update** | Daily | 2:30 AM | Update safe donation amounts |
| **Model Retraining** | Monthly | 1st of month, 3 AM | Retrain models with new data |

### 8.2 Job Dependencies

```
Ingestion (every 15 min)
    ↓
Daily Aggregation (12:30 AM)
    ↓
Current Month Predictions (1:00 AM)
    ↓
Next Month Predictions (1:30 AM)
    ↓
Pool Optimization (2:00 AM)
    ↓
Donation Threshold Update (2:30 AM)
```

### 8.3 Error Handling

**Failure Scenarios:**
- SFTP connection failure → Retry 3 times with exponential backoff
- Database deadlock → Retry transaction
- Model prediction failure → Use last known prediction + flag for manual review
- API timeout → Return cached data with `stale: true` flag

**Monitoring:**
- All jobs log to `etl_runs` table
- Failed jobs trigger email/Slack alerts
- Dashboard shows job health and last run times

---

## 9. Deployment Architecture

### 9.1 Azure Services

| Component | Azure Service | Configuration |
|-----------|---------------|---------------|
| **Database** | Azure Database for PostgreSQL (Flexible Server) | - TimescaleDB extension enabled<br>- 4 vCores, 16 GB RAM<br>- 128 GB SSD storage |
| **API** | Azure Container Apps | - Python FastAPI container<br>- Auto-scale 1-5 instances<br>- Health checks enabled |
| **Scheduled Jobs** | Azure Functions (Python) | - Consumption plan<br>- Timer triggers for each job<br>- App Insights logging |
| **File Storage** | Azure Blob Storage | - Store historical CDR/DSR files<br>- Lifecycle policy: move to cool tier after 30 days |
| **Monitoring** | Azure Monitor + App Insights | - Custom metrics dashboard<br>- Alerts on failures |

### 9.2 Environment Separation

**Development:**
- Local PostgreSQL + TimescaleDB
- Local Python environment
- Sample data (1000 subscribers)

**Staging:**
- Azure PostgreSQL (smaller instance)
- Subset of production data (5000 subscribers)
- Full job scheduling

**Production:**
- Full Azure deployment
- All 30-50K subscribers
- High availability enabled

---

## 10. Performance Targets

### 10.1 System Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Response Time** | < 200ms (p95) | All GET endpoints |
| **Prediction Latency** | < 1 second per subscriber | Batch prediction jobs |
| **Ingestion Throughput** | 10,000 CDRs/second | 15-min ingestion window |
| **Database Query Time** | < 50ms (p95) | User profile queries |

### 10.2 Accuracy Targets

| Model | Metric | Target |
|-------|--------|--------|
| **Current Month Predictor** | MAPE | < 15% |
| **Next Month Predictor** | MAPE | < 20% |
| **Pool Optimization** | Cost Savings | > 15% vs. no optimization |
| **Overage Prevention** | False Positive Rate | < 5% |

### 10.3 Scalability

**Current Capacity (30-50K subscribers):**
- Database: 100K+ reads/sec, 10K+ writes/sec
- API: 500 requests/sec
- Storage: 100 GB/month CDR data

**Future Growth (500K subscribers):**
- Scale database vertically (8 vCores, 32 GB RAM)
- Scale API horizontally (10+ container instances)
- Partition tables by subscriber hash

---

## 11. Security & Compliance

### 11.1 Data Security

**Encryption:**
- At rest: AES-256 encryption for database and blob storage
- In transit: TLS 1.2+ for all API and database connections
- SFTP: SSH key-based authentication

**Access Control:**
- Database: Role-based access (read-only for API, read-write for jobs)
- API: API key authentication with rate limiting
- Azure: Managed identities for service-to-service auth

### 11.2 Data Privacy

**PII Handling:**
- MSISDN, IMSI are pseudonymized in logs
- No storage of SMS content or call recordings
- GDPR-compliant data retention policies

**Audit Logging:**
- All pool tier changes logged with reason
- API access logs retained for 90 days
- Database query audit trail

---

## 12. Testing Strategy

### 12.1 Unit Testing

**Coverage Target:** > 80%

**Key Test Areas:**
- CDR/DSR parsers (handle malformed data)
- Aggregation functions (correct calculations)
- Model prediction functions (output validation)
- Pool optimization logic (cost calculations)
- API endpoints (input validation, error handling)

### 12.2 Integration Testing

**Test Scenarios:**
- End-to-end: SFTP → Database → Predictions → API
- Database triggers and functions
- Job scheduling and dependencies
- Error recovery and retry logic

### 12.3 Load Testing

**Targets:**
- 1000 concurrent API requests
- 100K CDR ingestion in 15 minutes
- 50K subscriber predictions in 5 minutes

**Tools:** Locust, pytest-benchmark

### 12.4 Validation Testing

**Data Quality:**
- Validate CDR parsing accuracy (100% of required fields)
- Check for data duplication
- Verify aggregation math

**Model Quality:**
- Backtesting with historical data
- A/B testing predictions vs. actuals
- Monitor prediction drift

---

## 13. Monitoring & Alerting

### 13.1 Metrics Dashboard

**System Health:**
- API uptime, response times
- Database connection pool status
- Job success/failure rates
- Data ingestion lag

**Business Metrics:**
- Total subscribers, active subscribers
- Pool tier distribution
- Total donations, total overage charges
- Cost savings from optimization

### 13.2 Alerts

**Critical (Immediate):**
- SFTP connection failed for 1+ hour
- Database unavailable
- API error rate > 5%
- Model prediction failure

**Warning (Daily Summary):**
- Job took >2x expected time
- Model MAPE > threshold
- Unusual subscriber churn

---

## 14. Documentation Deliverables

### 14.1 Technical Documentation

✅ **Database Schema** (`mvno_schema.sql`)
- All tables, indexes, triggers, functions documented

✅ **API Specification** (`docs/api_specs.md`)
- OpenAPI/Swagger documentation
- Request/response examples

✅ **Architecture Diagram** (This document)
- System components and data flow

### 14.2 Operational Documentation

📝 **Deployment Guide** (`docs/deployment.md`)
- Azure setup instructions
- Environment configuration

📝 **Runbooks** (`docs/runbooks.md`)
- How to handle common issues
- Job failure recovery

📝 **Model Training Guide** (`docs/model_training.md`)
- How to retrain models
- Feature engineering steps

---

## 15. Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **SFTP downtime** | High | Medium | Retry logic, alert after 1 hour, maintain local buffer |
| **Model accuracy degradation** | Medium | Low | Daily monitoring, automated alerts, monthly retraining |
| **Database performance** | High | Low | TimescaleDB partitioning, query optimization, caching |
| **API overload** | Medium | Medium | Rate limiting, auto-scaling, CDN for static content |
| **Data quality issues** | Medium | Medium | Validation checks, error logging, manual review queue |

---

## 16. Success Criteria

### 16.1 Milestone 1-2 Acceptance (This Document)

✅ Database schema approved
✅ Architecture design approved
✅ Model approach validated
✅ API specifications confirmed

### 16.2 Final System Acceptance

- [ ] All 3 prediction models operational with MAPE < targets
- [ ] Pool optimization saving > 15% vs. baseline
- [ ] API uptime > 99.5%
- [ ] Zero overage charges caused by incorrect predictions
- [ ] Complete documentation delivered
- [ ] Knowledge transfer completed

---

## 17. Timeline Confirmation

**Total Duration:** 12-14 days

- **Step 1-2 (Days 1-2):** Requirements + This Design Document ✅
- **Step 3 (Days 3-5):** Core Build (Ingestion + Models)
- **Step 4 (Days 6-9):** Optimization Engine
- **Step 5 (Days 10-14):** Testing + Deployment

**Target Completion:** February 11-13, 2026

---

## Appendix A: Sample Data Structures

### CDR Voice Record Example
```csv
206616,1,9182069189,3456789075436,VOICE_MO,HOME,2023-03-14 12:54:00,...
```

### DSR Record Example
```csv
"2023-09-13","2022100146","310240181838051","0","00000001","1","0","0","4","229625731.000",...
```

---

## Appendix B: Configuration Parameters

```env
# Tier Configuration
TIER_1_CAP_GB=5.0
TIER_1_COST=15.00
TIER_2_CAP_GB=10.0
TIER_2_COST=25.00
TIER_3_CAP_GB=20.0
TIER_3_COST=40.00

# Prediction Settings
CONFIDENCE_LEVEL=0.90
DONATION_SAFETY_BUFFER=0.10
OVERAGE_ALERT_THRESHOLD=0.90

# Performance
MAX_WORKERS=4
BATCH_SIZE=1000
CACHE_TTL_SECONDS=300
```

---

**Document Status:** APPROVED FOR IMPLEMENTATION  
**Next Steps:** Proceed to Step 3 (Core Build) upon client approval