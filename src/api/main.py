"""
MVNO Intelligence Hub - REST API
Serves usage, predictions, and donation data to the customer app.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from sqlalchemy import text

from config.database import engine
from config.logging_config import setup_logging
from src.models.realtime_predictor import get_full_realtime_profile
from src.models.current_month_predictor import predict_for_subscriber, save_prediction_to_db
from src.models.next_month_predictor import predict_next_month_for_subscriber, save_next_month_prediction_to_db
from src.features.usage_aggregation import get_subscriber_usage_summary, get_current_billing_cycle_dates
from src.optimization.donation_calculator import calculate_donation_for_subscriber

logger = setup_logging(__name__)

app = FastAPI(
    title="MVNO Intelligence Hub API",
    description="Usage prediction, pool optimization, and P2P donation system for Culture Wireless",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ─────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────

@app.get("/health")
def health_check():
    """API and database health check"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")


# ─────────────────────────────────────────
# USAGE ENDPOINTS
# ─────────────────────────────────────────

@app.get("/usage/{msisdn}/realtime")
def get_realtime_usage(msisdn: str):
    """
    Real-time usage profile for a subscriber.
    Returns current session data, velocity, and short-term projections.
    Updates every 15 minutes as CDR data arrives.
    """
    profile = get_full_realtime_profile(msisdn)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No data found for {msisdn}")
    return profile


@app.get("/usage/{msisdn}/summary")
def get_usage_summary(msisdn: str):
    """
    Month-to-date usage summary for a subscriber.
    Returns billing cycle dates, MTD usage, and daily velocity.
    """
    summary = get_subscriber_usage_summary(msisdn)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No usage summary found for {msisdn}")
    return summary


@app.get("/usage/{msisdn}/history")
def get_usage_history(msisdn: str, days: int = 30):
    """
    Daily usage history for a subscriber.
    """
    query = text("""
        SELECT
            usage_date,
            ROUND(data_bytes / 1073741824.0, 4) as data_gb,
            data_sessions,
            voice_minutes,
            sms_count
        FROM usage_daily_agg
        WHERE msisdn = :msisdn
        AND usage_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        ORDER BY usage_date DESC
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {'msisdn': msisdn, 'days': days}).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No history found for {msisdn}")
        return {
            'msisdn': msisdn,
            'days_requested': days,
            'records': [
                {
                    'date': str(row[0]),
                    'data_gb': float(row[1]),
                    'sessions': int(row[2]),
                    'voice_minutes': float(row[3]) if row[3] else 0,
                    'sms_count': int(row[4]) if row[4] else 0
                }
                for row in rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# PREDICTION ENDPOINTS
# ─────────────────────────────────────────

@app.get("/predictions/{msisdn}/current-month")
def get_current_month_prediction(msisdn: str, refresh: bool = False):
    """
    Current month end-of-cycle prediction for a subscriber.
    Returns predicted total GB, confidence intervals, and days remaining.
    Set refresh=true to retrain the model with latest data.
    """
    query = text("""
        SELECT
            predicted_data_gb, confidence_lower_gb, confidence_upper_gb,
            days_remaining, current_usage_gb, prediction_date, model_version
        FROM predictions_current_month
        WHERE msisdn = :msisdn
        ORDER BY prediction_date DESC
        LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {'msisdn': msisdn}).fetchone()

        # If refresh requested or no prediction exists, generate one
        if refresh or not row:
            result = predict_for_subscriber(msisdn, retrain=True)
            if result:
                save_prediction_to_db(result)
                return result
            raise HTTPException(status_code=500, detail="Failed to generate prediction")

        return {
            'msisdn': msisdn,
            'predicted_total_gb': float(row[0]),
            'confidence_lower_gb': float(row[1]) if row[1] else None,
            'confidence_upper_gb': float(row[2]) if row[2] else None,
            'days_remaining': int(row[3]) if row[3] else None,
            'current_usage_gb': float(row[4]) if row[4] else None,
            'prediction_date': str(row[5]),
            'model_version': row[6]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predictions/{msisdn}/next-month")
def get_next_month_prediction(msisdn: str, refresh: bool = False):
    """
    Next billing cycle prediction for donation planning.
    Returns predicted GB for next month with confidence intervals.
    """
    query = text("""
        SELECT
            predicted_data_gb, confidence_lower_gb, confidence_upper_gb,
            next_month, created_at, model_version
        FROM predictions_next_month
        WHERE msisdn = :msisdn
        ORDER BY created_at DESC
        LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {'msisdn': msisdn}).fetchone()

        if refresh or not row:
            result = predict_next_month_for_subscriber(msisdn, retrain=True)
            if result:
                save_next_month_prediction_to_db(result)
                return result
            raise HTTPException(status_code=500, detail="Failed to generate next month prediction")

        return {
            'msisdn': msisdn,
            'predicted_next_month_gb': float(row[0]),
            'confidence_lower_gb': float(row[1]) if row[1] else None,
            'confidence_upper_gb': float(row[2]) if row[2] else None,
            'next_month_start': str(row[3]),
            'generated_at': str(row[4]),
            'model_version': row[5]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predictions/{msisdn}/all")
def get_all_predictions(msisdn: str):
    """
    Full prediction profile for the customer app user profile.
    Returns real-time, current month, and next month in one call.
    """
    realtime = get_full_realtime_profile(msisdn)
    current = get_current_month_prediction(msisdn)
    next_month = get_next_month_prediction(msisdn)
    billing_start, billing_end = get_current_billing_cycle_dates()

    return {
        'msisdn': msisdn,
        'as_of': datetime.now().isoformat(),
        'billing_cycle': {
            'start': str(billing_start),
            'end': str(billing_end)
        },
        'realtime': realtime,
        'current_month': current,
        'next_month': next_month
    }


# ─────────────────────────────────────────
# DONATION ENDPOINTS
# ─────────────────────────────────────────

@app.get("/donations/{msisdn}/threshold")
def get_donation_threshold(msisdn: str):
    """
    How much data a subscriber can safely donate this cycle.
    """
    donation = calculate_donation_for_subscriber(msisdn)
    if not donation:
        raise HTTPException(status_code=404, detail=f"No donation data available for {msisdn}")
    return donation


@app.get("/donations/{msisdn}/history")
def get_donation_history(msisdn: str):
    """
    Donation history for a subscriber (as donor and recipient).
    """
    query = text("""
        SELECT
            id, donor_msisdn, recipient_msisdn,
            amount_gb, transaction_date, status
        FROM data_donations
        WHERE donor_msisdn = :msisdn OR recipient_msisdn = :msisdn
        ORDER BY transaction_date DESC
        LIMIT 50
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {'msisdn': msisdn}).fetchall()
        return {
            'msisdn': msisdn,
            'donations': [
                {
                    'id': row[0],
                    'donor': row[1],
                    'recipient': row[2],
                    'amount_gb': float(row[3]),
                    'date': str(row[4]),
                    'status': row[5],
                    'role': 'donor' if row[1] == msisdn else 'recipient'
                }
                for row in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/donations/community/impact")
def get_community_impact():
    """
    Community-wide donation impact for the current billing cycle.
    """
    billing_start, billing_end = get_current_billing_cycle_dates()
    query = text("""
        SELECT
            COUNT(DISTINCT recipient_msisdn) as subscribers_saved,
            COALESCE(SUM(amount_gb), 0) as total_gb_redistributed,
            COALESCE(SUM(amount_gb) * 10, 0) as estimated_savings_usd,
            COUNT(*) as total_transactions
        FROM data_donations
        WHERE transaction_date::date >= :billing_start
        AND transaction_date::date <= :billing_end
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {
                'billing_start': billing_start,
                'billing_end': billing_end
            }).fetchone()
        return {
            'billing_cycle': {
                'start': str(billing_start),
                'end': str(billing_end)
            },
            'subscribers_saved': int(row[0]),
            'total_gb_redistributed': float(row[1]),
            'estimated_savings_usd': float(row[2]),
            'total_transactions': int(row[3])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# POOL ENDPOINTS
# ─────────────────────────────────────────

@app.get("/pool/{msisdn}/assignment")
def get_pool_assignment(msisdn: str):
    """
    Current pool tier assignment for a subscriber.
    """
    billing_start, _ = get_current_billing_cycle_dates()
    query = text("""
        SELECT
            pa.tier_id, pt.tier_name, pt.data_cap_gb,
            pa.billing_month, pa.assigned_date
        FROM pool_assignments pa
        JOIN pool_tiers pt ON pa.tier_id = pt.tier_id
        WHERE pa.msisdn = :msisdn
        AND pa.billing_month = :billing_month
        ORDER BY pa.assigned_date DESC
        LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {
                'msisdn': msisdn,
                'billing_month': billing_start.strftime('%Y-%m')
            }).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No pool assignment found for {msisdn}")
        return {
            'msisdn': msisdn,
            'tier_id': int(row[0]),
            'tier_name': row[1],
            'data_cap_gb': float(row[2]),
            'billing_month': row[3],
            'assigned_date': str(row[4])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
