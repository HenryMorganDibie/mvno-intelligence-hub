# MVNO Usage Prediction System - Architecture Document

**Project:** MVNO Usage Prediction & Pool Optimization  
**Client:** Culture Wireless Group  
**Date:** January 30, 2026  
**Version:** 1.1 (Updated with billing cycle information)

---

## 📋 Executive Summary

This system processes Call Detail Records (CDR) and Daily Subscriber Reports (DSR) to predict subscriber usage, optimize data pool assignments, and calculate safe donation thresholds.

**Billing Cycle Context:**
- **Invoice Generation:** 21st of each month
- **Invoice Period:** 21st to 20th (e.g., Jan 21 - Feb 20)
- **Payment Terms:** 20 days
- **Invoice Email:** Sent within 5 business days from message-service@sender.zohobooks.com

**Key Deliverables:**
- Real-time, current month, and next month usage predictions
- Automated pool tier optimization
- Data donation threshold calculations
- REST API for user profile integration

---

## 🎯 Visual Data Flow (Simplified for Non-Technical Team)

```
┌────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                               │
│                                                                    │
│  Every 15 Minutes:              Monthly (End of Billing Cycle):   │
│  ┌──────────────┐               ┌──────────────────┐             │
│  │ Daily Usage  │               │  Monthly Usage   │             │
│  │    Files     │               │  Files (Invoice  │             │
│  │  (15-min)    │               │  Reconciliation) │             │
│  └──────────────┘               └──────────────────┘             │
│         │                                  │                      │
│         └──────────────┬───────────────────┘                      │
└────────────────────────┼───────────────────────────────────────────┘
                         │
                         │ Secure SFTP Transfer
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                    OUR SYSTEM (CLOUD)                              │
│                                                                    │
│   Step 1: COLLECT                                                 │
│   ┌────────────────────────────────────────────┐                 │
│   │  • Download files from carrier             │                 │
│   │  • Parse Voice, SMS, Data records          │                 │
│   │  • Store in database                       │                 │
│   └────────────────────────────────────────────┘                 │
│                         │                                         │
│                         ▼                                         │
│   Step 2: ANALYZE                                                 │
│   ┌────────────────────────────────────────────┐                 │
│   │  • Calculate total usage per subscriber    │                 │
│   │  • Track trends and patterns               │                 │
│   │  • Identify unusual behavior               │                 │
│   └────────────────────────────────────────────┘                 │
│                         │                                         │
│                         ▼                                         │
│   Step 3: PREDICT                                                 │
│   ┌────────────────────────────────────────────┐                 │
│   │  AI Models predict:                        │                 │
│   │  • How much data will be used by month-end │                 │
│   │  • How much will be used next month        │                 │
│   │  • If customer will go over their limit    │                 │
│   └────────────────────────────────────────────┘                 │
│                         │                                         │
│                         ▼                                         │
│   Step 4: OPTIMIZE                                                │
│   ┌────────────────────────────────────────────┐                 │
│   │  • Assign customers to best data pool      │                 │
│   │  • Calculate safe donation amounts         │                 │
│   │  • Minimize costs, prevent overages        │                 │
│   └────────────────────────────────────────────┘                 │
│                         │                                         │
└─────────────────────────┼──────────────────────────────────────────┘
                          │
                          │ Real-time API
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    CUSTOMER MOBILE APP                             │
│                                                                    │
│   Customer sees:                                                  │
│   ┌────────────────────────────────────────────┐                 │
│   │  • Current usage this month: 6.2 GB        │                 │
│   │  • Predicted total: 8.5 GB                 │                 │
│   │  • Safe to donate: 2.3 GB                  │                 │
│   │  • Data pool: Tier 2 (10 GB)               │                 │
│   └────────────────────────────────────────────┘                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## 📅 Billing Cycle & Data Flow Timeline

### Monthly Cycle Overview

```
Day 1-20: Active Billing Period
├─ Every 15 minutes: Daily usage files received
├─ Every day: Predictions updated
└─ Real-time: Customer app shows live data

Day 21: Invoice Generation
├─ Monthly usage file received (for reconciliation)
├─ Invoice emailed within 5 business days
└─ New billing cycle begins

Day 21-41: Payment Period (20 days)
└─ Invoice payment due
```

### Data File Types

| File Type | Frequency | Purpose | When Used |
|-----------|-----------|---------|-----------|
| **Daily Usage Files** | Every 15 minutes | Real-time tracking, predictions | Continuously during billing cycle |
| **Monthly Usage Files** | End of billing cycle (21st) | Invoice reconciliation | Monthly, for final billing |

**Key Point:** Daily files (every 15 min) are used for predictions and customer app. Monthly files are the official records for invoicing.

---

## 🔄 System Data Flow (Technical)

```
┌─────────────────────────────────────────────────────────────────┐
│                     SFTP Server (Every 15 mins)                 │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐     │
│  │  CDR Files   │  │  DSR Files   │  │  Monthly Files   │     │
│  │ Voice/SMS/   │  │  (Subscriber │  │  (Billing Cycle  │     │
│  │    Data      │  │   Snapshots) │  │    Complete)     │     │
│  └──────────────┘  └──────────────┘  └──────────────────┘     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Ingestion Pipeline                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ SFTP Client  │→ │ File Parser  │→ │  Validator   │         │
│  │              │  │ (CSV → JSON) │  │ (Quality     │         │
│  │              │  │              │  │  Checks)     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (TimescaleDB)                  │
│                                                                 │
│  Raw Data Storage:                                             │
│  ┌─────────────────────────────────────────────┐              │
│  │ • cdr_voice (calls)                         │              │
│  │ • cdr_sms (text messages)                   │              │
│  │ • cdr_data (internet usage)                 │              │
│  │ • daily_subscriber_reports (daily snapshots)│              │
│  └─────────────────────────────────────────────┘              │
│                        │                                       │
│  Aggregated Data:      ▼                                       │
│  ┌─────────────────────────────────────────────┐              │
│  │ • usage_daily_agg (daily totals per user)   │              │
│  │ • usage_monthly_agg (monthly totals)        │              │
│  └─────────────────────────────────────────────┘              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ML Prediction Engine                          │
│                                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │  Model 1: Real-Time Predictor            │                 │
│  │  • Predicts next 15-60 mins              │                 │
│  │  • Updates every 15 mins                 │                 │
│  │  • Alerts if approaching limit           │                 │
│  └──────────────────────────────────────────┘                 │
│                                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │  Model 2: Current Month Predictor        │                 │
│  │  • Predicts total usage by month-end     │                 │
│  │  • Updates daily at 1 AM                 │                 │
│  │  • Confidence intervals (90%)            │                 │
│  └──────────────────────────────────────────┘                 │
│                                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │  Model 3: Next Month Predictor           │                 │
│  │  • Predicts next billing cycle usage     │                 │
│  │  • For donation planning                 │                 │
│  │  • Updated daily at 1:30 AM              │                 │
│  └──────────────────────────────────────────┘                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Pool Optimization & Donation Engine                │
│                                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │  Pool Optimizer (Runs Daily at 2 AM)     │                 │
│  │  • Assigns users to Tier 1/2/3           │                 │
│  │  • Minimizes costs                       │                 │
│  │  • Prevents overages                     │                 │
│  └──────────────────────────────────────────┘                 │
│                                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │  Donation Calculator (Runs Daily 2:30 AM)│                 │
│  │  • Calculates safe donation amount       │                 │
│  │  • Allocated - Predicted - Buffer        │                 │
│  │  • Updates customer app                  │                 │
│  └──────────────────────────────────────────┘                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      REST API (FastAPI)                         │
│                                                                 │
│  Endpoints for Customer App:                                   │
│  ┌──────────────────────────────────────────┐                 │
│  │  GET /usage/{phone}                      │                 │
│  │  GET /predictions/{phone}/current-month  │                 │
│  │  GET /donations/{phone}/threshold        │                 │
│  │  POST /donations                         │                 │
│  └──────────────────────────────────────────┘                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Customer Mobile App                          │
│                (Culture Wireless App)                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 💡 How The System Works (Plain English)

### For Customers:

1. **You use your phone** (calls, texts, data)
2. **Carrier records everything** (every 15 minutes)
3. **Our system gets the data** (automatically via SFTP)
4. **AI predicts your usage** (will you go over? how much can you donate?)
5. **Your app shows you:**
   - Current usage: "You've used 6.2 GB this month"
   - Prediction: "You'll likely use 8.5 GB total"
   - Safe to donate: "You can donate 2.3 GB without risk"

### For Operations Team:

1. **Data arrives every 15 minutes** from the carrier
2. **System processes automatically:**
   - Parses files (Voice, SMS, Data)
   - Stores in database
   - Calculates daily totals
3. **Every night:**
   - AI updates predictions
   - Pool optimizer reassigns users to best tier
   - Donation thresholds updated
4. **Monthly (21st):**
   - Monthly file received
   - Used for invoice reconciliation
   - New billing cycle starts

---

## 🗄️ Database Design

### Core Tables

**Subscribers Table**
- Master list of all customers
- Phone number, IMSI, activation date, current status
- Which data pool tier they're in

**Daily Subscriber Reports (DSR)**
- Snapshot of each customer every 15 minutes
- Voice minutes, SMS count, Data bytes
- Current status (active/suspended)

**Call Detail Records (CDR)**
- Detailed record of every call, text, data session
- Three separate tables: Voice, SMS, Data
- Used for granular analysis

**Usage Aggregations**
- Daily totals per customer (fast queries)
- Monthly running totals (automatically updated)

**Predictions**
- Real-time forecasts (15-min, 30-min, 1-hour)
- Current month predictions (updated daily)
- Next month predictions

**Pool Management**
- Tier definitions (Tier 1: 5GB, Tier 2: 10GB, Tier 3: 20GB)
- Assignment history (who moved when and why)
- Optimization logs (cost savings tracked)

**Donations**
- Safe donation thresholds
- Actual donations made
- Reward points earned

---

## 📊 Data Processing Schedule

### Continuous (Every 15 Minutes)
- Download new CDR/DSR files from carrier
- Parse and load into database
- Update real-time predictions
- Check for usage alerts

### Daily (Overnight)

| Time | Job | Purpose |
|------|-----|---------|
| 12:30 AM | Daily Aggregation | Calculate yesterday's totals |
| 1:00 AM | Current Month Predictions | Update "how much will you use?" |
| 1:30 AM | Next Month Predictions | Plan ahead for next cycle |
| 2:00 AM | Pool Optimization | Move users to best tier |
| 2:30 AM | Donation Thresholds | Update "safe to donate" amounts |

### Monthly (21st of Month)
- Receive monthly usage file from carrier
- Reconcile with our daily totals
- Generate invoice data
- Archive old CDRs (keep aggregates)

---

## 🎯 Pool Optimization Strategy

### Three Data Tiers

| Tier | Data Cap | Cost per User | When to Use |
|------|----------|---------------|-------------|
| **Tier 1** | 5 GB | $15/month | Light users (predicted < 4.5 GB) |
| **Tier 2** | 10 GB | $25/month | Medium users (predicted 4.5-9 GB) |
| **Tier 3** | 20 GB | $40/month | Heavy users (predicted > 9 GB) |

### Assignment Logic

**Daily Process:**
1. Get prediction for each customer (e.g., "will use 6.8 GB")
2. Add safety buffer (10%): 6.8 × 1.1 = 7.48 GB needed
3. Assign to cheapest tier that fits: Tier 2 (10 GB)
4. Track cost savings vs. "everyone in Tier 3"

**Example:**
- 30,000 customers
- Without optimization: All in Tier 3 = 30,000 × $40 = $1,200,000
- With optimization: 
  - 15,000 in Tier 1 = $225,000
  - 10,000 in Tier 2 = $250,000
  - 5,000 in Tier 3 = $200,000
  - **Total: $675,000**
  - **Savings: $525,000 (44%)**

---

## 🎁 Donation System

### How It Works

**Safe Donation Formula:**
```
Safe Amount = Tier Capacity - Predicted Usage - Safety Buffer

Example:
- Customer has Tier 2 (10 GB)
- Predicted to use: 6.5 GB
- Safety buffer: 1.0 GB (90% confidence)
- Safe to donate: 10 - 6.5 - 1.0 = 2.5 GB
```

**In the App:**
- "You can safely donate up to 2.5 GB"
- Earn 2.5 reward points
- Helps other customers avoid overages
- Recalculated daily as usage changes

**What Happens:**
1. Customer donates 2 GB
2. Recipient gets 2 GB added to their account
3. Donor gets 2 reward points
4. Donor's new safe amount: 2.5 - 2.0 = 0.5 GB
5. System tracks all donations for billing

---

## 🔒 Data Security

### What We Protect

**Sensitive Data:**
- Customer phone numbers (MSISDN)
- Usage patterns
- Location data (cell tower IDs)
- Personal information

**How We Protect:**
- Encryption at rest (database)
- Encryption in transit (HTTPS, SFTP)
- Access controls (role-based)
- Audit logs (who accessed what)
- No storage of SMS content or call recordings

**Compliance:**
- GDPR-compliant data retention (delete on request)
- PII pseudonymization in logs
- 90-day retention for raw CDRs
- Longer retention for aggregates (de-identified)

---

## 📈 Performance Targets

### System Speed

| Metric | Target | What It Means |
|--------|--------|---------------|
| **API Response** | < 200ms | Customer app loads fast |
| **Prediction Update** | < 1 second/customer | Daily predictions finish quickly |
| **File Ingestion** | < 5 minutes | Process 15-min file batch |
| **Database Query** | < 50ms | App is responsive |

### Accuracy Targets

| Model | Target Accuracy | What It Means |
|-------|----------------|---------------|
| **Current Month** | Within 15% | If we predict 10 GB, actual is 8.5-11.5 GB |
| **Next Month** | Within 20% | Longer horizon = wider range |
| **Overage Prevention** | > 95% | Rarely assign tier that's too small |

---

## 🚀 Technology Stack

### Core Technologies

| Component | Technology | Why We Chose It |
|-----------|-----------|-----------------|
| **Database** | PostgreSQL + TimescaleDB | Best for time-series data (CDRs) |
| **Backend** | Python 3.9+ | Rich ML libraries, fast development |
| **API** | FastAPI | High performance, auto-documentation |
| **ML** | Prophet, XGBoost | Proven forecasting algorithms |
| **Cloud** | Azure | Existing infrastructure |
| **Scheduling** | Azure Functions | Serverless, cost-effective |

---

## 📝 Deliverables Checklist

### Phase 1: Design (CURRENT - Milestone 1-2)
- ✅ Database schema designed
- ✅ Architecture documented
- ✅ Data flow visualized
- ✅ ML approach validated
- ⏳ Awaiting client approval

### Phase 2: Core Build (Milestone 3)
- [ ] SFTP ingestion working
- [ ] CDR/DSR parsers complete
- [ ] Database populated with sample data
- [ ] Daily aggregations working

### Phase 3: ML & Optimization (Milestone 4)
- [ ] All 3 prediction models trained
- [ ] Pool optimizer operational
- [ ] Donation calculator working
- [ ] Accuracy validated

### Phase 4: API & Deployment (Milestone 5)
- [ ] REST API endpoints live
- [ ] Azure deployment complete
- [ ] Documentation finished
- [ ] System tested and validated

---

## 🎯 Success Metrics

### Business Goals

1. **Cost Savings:** Save > 15% vs. no optimization
2. **Customer Satisfaction:** < 1% overage incidents
3. **System Reliability:** 99.5% uptime
4. **Prediction Accuracy:** Within target ranges

### Technical Goals

1. **Data Quality:** 100% of CDR files processed successfully
2. **Performance:** All API calls < 200ms
3. **Scalability:** Handle 50K users with room to grow
4. **Maintainability:** Clear code, full documentation

---

## 📞 Questions & Next Steps

### For Approval

**Please confirm:**
1. Billing cycle dates are correct (21st to 20th)
2. Three-tier pool structure is accurate
3. Data flow diagram makes sense to non-technical team
4. Monthly file usage for reconciliation is clear

### After Approval

**We'll proceed to:**
1. Set up Azure infrastructure
2. Build SFTP ingestion pipeline
3. Implement CDR/DSR parsers
4. Load sample data for testing

---

## 📚 Additional Resources

### Documentation Structure

```
docs/
├── architecture.md          ← This document
├── api_specifications.md    ← Detailed API docs
├── deployment_guide.md      ← Azure setup instructions
└── user_guide.md            ← How to use the system
```

### Support

**For questions about:**
- Technical architecture → Henry Dibie
- Business requirements → Account Manager
- Billing cycle details → Culture Wireless Operations

---

**Document Status:** Ready for Client Review  
**Version:** 1.1 (Updated with billing cycle information)  
**Last Updated:** January 30, 2026

**Next Step:** Client approval to proceed to Milestone 3 (Core Build)