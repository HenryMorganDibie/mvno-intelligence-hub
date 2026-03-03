"""
Pipeline Health Monitor
Checks system health and alerts if anything is broken.
Designed to run after every main.py execution or on a cron schedule.
"""

import os
from datetime import datetime, timedelta
from sqlalchemy import text
from config.database import engine
from config.logging_config import setup_logging

logger = setup_logging(__name__)

ALERT_LOG = "logs/health_alerts.log"


def log_alert(message):
    """Write critical alerts to a dedicated alert log"""
    os.makedirs("logs", exist_ok=True)
    with open(ALERT_LOG, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] ALERT: {message}\n")
    logger.critical(f"🚨 ALERT: {message}")


def check_sftp_ingestion():
    """Verify new DSR data arrived in the last 48 hours"""
    query = text("""
        SELECT MAX(usage_date) as latest_date,
               COUNT(*) as records_last_48h
        FROM daily_subscriber_reports
        WHERE usage_date >= CURRENT_DATE - INTERVAL '2 days'
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
        latest_date = row[0]
        recent_count = row[1]

    if not latest_date:
        log_alert("No DSR data found at all in daily_subscriber_reports")
        return False

    days_since = (datetime.now().date() - latest_date).days
    if days_since > 2:
        log_alert(f"DSR data is stale - last record was {days_since} days ago ({latest_date})")
        return False

    if recent_count == 0:
        log_alert("No new DSR records in the last 48 hours - SFTP ingestion may be failing")
        return False

    logger.info(f"✅ SFTP Ingestion OK - {recent_count} records in last 48h, latest: {latest_date}")
    return True


def check_predictions_fresh():
    """Verify predictions were generated today"""
    query = text("""
        SELECT COUNT(*) as today_count,
               COUNT(DISTINCT msisdn) as subscribers_predicted
        FROM predictions_current_month
        WHERE prediction_date = CURRENT_DATE
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
        today_count = row[0]
        subscribers = row[1]

    if today_count == 0:
        log_alert("No predictions generated today - pipeline may have failed")
        return False

    logger.info(f"✅ Predictions OK - {subscribers} subscribers predicted today")
    return True


def check_predictions_complete():
    """Verify predictions have all required fields populated"""
    query = text("""
        SELECT COUNT(*) as incomplete
        FROM predictions_current_month
        WHERE prediction_date = CURRENT_DATE
        AND (
            confidence_upper_gb IS NULL OR
            confidence_lower_gb IS NULL OR
            current_usage_gb IS NULL OR
            days_remaining IS NULL
        )
    """)
    with engine.connect() as conn:
        incomplete = conn.execute(query).scalar()

    if incomplete > 0:
        log_alert(f"{incomplete} predictions today are missing required fields")
        return False

    logger.info("✅ Prediction completeness OK - all fields populated")
    return True


def check_aggregation_current():
    """Verify usage aggregation ran today"""
    query = text("""
        SELECT COUNT(DISTINCT msisdn) as subscribers_aggregated,
               MAX(updated_at) as last_updated
        FROM usage_daily_agg
        WHERE updated_at >= NOW() - INTERVAL '24 hours'
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
        count = row[0]
        last_updated = row[1]

    if count == 0:
        log_alert("Usage aggregation has not run in the last 24 hours")
        return False

    logger.info(f"✅ Aggregation OK - {count} subscribers updated, last run: {last_updated}")
    return True


def check_donation_matching():
    """Verify donation matching ran today if there were at-risk subscribers"""
    query = text("""
        SELECT COUNT(*) as donations_today,
               COALESCE(SUM(amount_gb), 0) as gb_matched
        FROM data_donations
        WHERE transaction_date::date = CURRENT_DATE
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
        donations = row[0]
        gb_matched = row[1]

    # Not an error if 0 donations - just means no one was at risk
    logger.info(f"✅ Donation Matching OK - {donations} donations today ({gb_matched:.2f} GB matched)")
    return True


def check_database_connectivity():
    """Basic DB connection test"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connectivity OK")
        return True
    except Exception as e:
        log_alert(f"Database connection failed: {e}")
        return False


def check_subscriber_growth():
    """Flag if subscriber count dropped unexpectedly"""
    query = text("""
        SELECT COUNT(*) as total_subscribers,
               SUM(CASE WHEN current_status = 'ACTIVE' THEN 1 ELSE 0 END) as active
        FROM subscribers
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
        total = row[0]
        active = row[1]

    if total == 0:
        log_alert("Subscriber table is empty - data may have been wiped")
        return False

    logger.info(f"✅ Subscriber Count OK - {total} total, {active} active")
    return True


def run_health_check():
    """Run all health checks and return overall status"""
    print("\n" + "="*55)
    print("  MVNO INTELLIGENCE HUB - HEALTH CHECK")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)

    checks = {
        "Database Connectivity":    check_database_connectivity,
        "SFTP Ingestion":           check_sftp_ingestion,
        "Usage Aggregation":        check_aggregation_current,
        "Predictions Fresh":        check_predictions_fresh,
        "Predictions Complete":     check_predictions_complete,
        "Donation Matching":        check_donation_matching,
        "Subscriber Count":         check_subscriber_growth,
    }

    results = {}
    for name, check_fn in checks.items():
        try:
            results[name] = check_fn()
        except Exception as e:
            log_alert(f"Health check '{name}' crashed: {e}")
            results[name] = False

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    failed = [name for name, v in results.items() if not v]

    print("\n" + "-"*55)
    print(f"  RESULT: {passed}/{total} checks passed")
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
        print(f"  See {ALERT_LOG} for details")
    else:
        print("  STATUS: ✅ All systems operational")
    print("="*55 + "\n")

    return len(failed) == 0


if __name__ == "__main__":
    run_health_check()
