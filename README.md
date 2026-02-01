# MVNO Usage Prediction & Pool Optimization System

A production-grade system for predicting subscriber usage patterns, optimizing data pool assignments, and calculating safe donation thresholds for an MVNO cellular service.

## 📋 Project Overview

This system processes Call Detail Records (CDR) and Daily Subscriber Reports (DSR) to:
- **Predict usage** at multiple horizons (real-time, current month, next month)
- **Optimize pool assignments** to minimize costs while preventing overages
- **Calculate donation thresholds** for data sharing between subscribers
- **Provide API endpoints** for integration with user-facing applications

## 🏗️ Architecture

```
SFTP (15-min intervals)
    ↓
Data Ingestion Pipeline
    ↓
PostgreSQL + TimescaleDB
    ↓
Feature Engineering
    ↓
ML Prediction Models ──→ Pool Optimizer ──→ Donation Calculator
    ↓                         ↓                    ↓
FastAPI Endpoints ←──────────┴────────────────────┘
    ↓
User Profile Dashboard
```

### Components

1. **Data Ingestion** (`src/ingestion/`)
   - SFTP client for file retrieval
   - CDR/DSR parsers (Voice, SMS, Data)
   - Database loaders

2. **Database** (`src/database/`)
   - TimescaleDB for time-series data
   - Optimized schema with hypertables
   - Automated aggregations

3. **ML Models** (`src/models/`)
   - Real-time predictor (15-min to 1-hour)
   - Current month predictor (updated daily)
   - Next month predictor

4. **Optimization** (`src/optimization/`)
   - Pool tier assignment
   - Cost minimization logic
   - Donation threshold calculation

5. **API** (`src/api/`)
   - FastAPI REST endpoints
   - User profile data
   - Real-time predictions

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 14+ with TimescaleDB extension
- SFTP access credentials

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd mvno-usage-prediction
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

5. **Initialize database**
```bash
# Create database
createdb mvno_usage_db

# Run schema
psql -d mvno_usage_db -f mvno_schema.sql
```

6. **Load sample data** (for testing)
```bash
python scripts/load_sample_data.py
```

## 📊 Database Schema

### Core Tables

- **subscribers**: Master subscriber table
- **daily_subscriber_reports**: DSR snapshots (TimescaleDB hypertable)
- **cdr_voice**, **cdr_sms**, **cdr_data**: Call detail records (TimescaleDB hypertables)
- **usage_daily_agg**: Pre-aggregated daily usage
- **usage_monthly_agg**: Running monthly totals

### Prediction Tables

- **predictions_realtime**: 15-min to 1-hour forecasts
- **predictions_current_month**: End-of-month predictions (updated daily)
- **predictions_next_month**: Next billing cycle predictions

### Optimization Tables

- **pool_tiers**: Data pool tier definitions (caps, costs)
- **pool_assignments**: Historical tier assignments
- **donation_thresholds**: Safe donation amounts
- **donations**: Actual donation transactions

## 🔧 Configuration

### Pool Tiers

Edit `pool_tiers` table or use environment variables:

```env
TIER_1_CAP_GB=5.0
TIER_1_COST=15.00
TIER_2_CAP_GB=10.0
TIER_2_COST=25.00
TIER_3_CAP_GB=20.0
TIER_3_COST=40.00
```

### Prediction Settings

```env
CONFIDENCE_LEVEL=0.90  # 90% confidence interval
DONATION_SAFETY_BUFFER=0.10  # 10% safety buffer
```

## 📡 API Endpoints

### Usage
- `GET /api/usage/{msisdn}` - Current month usage
- `GET /api/usage/{msisdn}/history` - Historical usage

### Predictions
- `GET /api/predictions/{msisdn}/realtime` - Real-time forecast
- `GET /api/predictions/{msisdn}/current-month` - Current month prediction
- `GET /api/predictions/{msisdn}/next-month` - Next month prediction

### Donations
- `GET /api/donations/{msisdn}/threshold` - Safe donation amount
- `POST /api/donations` - Record a donation

### Pool
- `GET /api/pool/{msisdn}/assignment` - Current pool tier
- `GET /api/pool/optimization/summary` - Optimization metrics

## 🔄 Scheduled Jobs

The system runs automated tasks:

1. **Every 15 minutes**: Ingest new CDR/DSR files from SFTP
2. **Daily at 1 AM**: Update current month predictions
3. **Daily at 2 AM**: Run pool optimization
4. **Daily at 3 AM**: Calculate donation thresholds

Configure in `.env`:
```env
INGESTION_INTERVAL_MINUTES=15
PREDICTION_UPDATE_HOUR=1
OPTIMIZATION_UPDATE_HOUR=2
```

## 🧪 Testing

Run tests:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=src tests/
```

## 📈 Model Details

### Real-Time Predictor
- **Algorithm**: Prophet
- **Horizon**: 15-min, 30-min, 60-min
- **Update frequency**: Every ingestion cycle
- **Features**: Recent usage velocity, time-of-day patterns

### Current Month Predictor
- **Algorithm**: Ensemble (Prophet + XGBoost)
- **Update frequency**: Daily
- **Features**: MTD usage, historical patterns, day-of-month, remaining days

### Next Month Predictor
- **Algorithm**: Prophet with seasonality
- **Update frequency**: Daily
- **Features**: Historical monthly usage, trends, subscriber characteristics

## 🚢 Deployment

### Local Development
```bash
uvicorn src.api.main:app --reload --port 8000
```

### Production (Azure)
See `docs/deployment.md` for detailed Azure deployment instructions.

## 📊 Monitoring

Monitor system health via:
- `etl_runs` table - ETL job status
- `model_metrics` table - Model performance
- API logs - Request/response tracking

## 🔐 Security

- Store credentials in `.env` (never commit)
- Use PostgreSQL connection pooling
- Validate all API inputs
- Implement rate limiting in production

## 📝 License

Proprietary - Culture Wireless Group

## 👥 Contributors

- Henry Dibie - Lead Developer

## 📞 Support

For issues or questions, contact: 

## 🗂️ Project Structure

```
mvno-usage-prediction/
├── config/                 # Configuration modules
├── data/                   # Data storage
│   ├── raw/               # Raw CDR/DSR files
│   ├── processed/         # Cleaned data
│   └── sample/            # Sample test data
├── src/                    # Source code
│   ├── ingestion/         # Data ingestion
│   ├── database/          # Database operations
│   ├── features/          # Feature engineering
│   ├── models/            # ML models
│   ├── optimization/      # Pool optimization
│   └── api/               # FastAPI application
├── scripts/               # Utility scripts
├── tests/                 # Unit tests
├── notebooks/             # Jupyter notebooks
├── docs/                  # Documentation
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
├── requirements.txt       # Python dependencies
├── mvno_schema.sql        # Database schema
└── README.md              # This file
```

## 🎯 Development Milestones

- [x] Step 1: Requirements & Data Review
- [x] Step 2: Technical Design & Schema
- [x] Step 3: Core Build (Phase 1: Ingestion & Parsing)
- [ ] Step 3: Core Build (Phase 2: Forecasting Models)
- [ ] Step 4: Optimization Engine
- [ ] Step 5: Testing & Deployment

## 📚 Additional Documentation

- [Architecture Details](docs/architecture.md)
- [API Specifications](docs/api_specs.md)
- [Deployment Guide](docs/deployment.md)
- [Model Training](docs/model_training.md)