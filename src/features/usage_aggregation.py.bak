"""
Usage Aggregation Module
Calculates daily and monthly usage totals per subscriber.
Production-ready: Uses centralized logging, database, and settings.
"""

from datetime import datetime, timedelta
from sqlalchemy import text
import logging

# 1. Professional Imports - No more hardcoded logging or env loads here
from config.logging_config import setup_logging
from config.database import engine

# Initialize professional logger
logger = setup_logging(__name__)

def aggregate_daily_usage(msisdn, usage_date):
    """Calculate total usage for a subscriber on a specific day"""
    query = text("""
        SELECT 
            :msisdn as msisdn,
            :usage_date as usage_date,
            COALESCE(SUM(voice.duration_minutes), 0) as voice_minutes,
            COALESCE(COUNT(DISTINCT sms.id), 0) as sms_count,
            COALESCE(SUM(data.total_volume_bytes), 0) as data_bytes,
            COUNT(DISTINCT voice.id) as voice_events,
            COUNT(DISTINCT sms.id) as sms_events,
            COUNT(DISTINCT data.id) as data_sessions
        FROM 
            (SELECT :msisdn as msisdn) sub
        LEFT JOIN cdr_voice voice 
            ON voice.msisdn = :msisdn 
            AND DATE(voice.effective_date) = :usage_date
        LEFT JOIN cdr_sms sms 
            ON sms.msisdn = :msisdn 
            AND DATE(sms.effective_date) = :usage_date
        LEFT JOIN cdr_data data 
            ON data.msisdn = :msisdn 
            AND DATE(data.effective_date) = :usage_date
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {'msisdn': msisdn, 'usage_date': usage_date})
            row = result.fetchone()
            if row:
                return {
                    'msisdn': row[0],
                    'usage_date': row[1],
                    'voice_minutes': float(row[2]),
                    'sms_count': int(row[3]),
                    'data_bytes': float(row[4]),
                    'voice_events': int(row[5]),
                    'sms_events': int(row[6]),
                    'data_sessions': int(row[7])
                }
    except Exception as e:
        logger.error(f"Error daily aggregation for {msisdn}: {e}")
    return None

def aggregate_monthly_usage(msisdn, billing_month):
    """Calculate month-to-date usage for a subscriber"""
    billing_start = datetime.strptime(billing_month, '%Y-%m-%d')
    if billing_start.day != 21:
        billing_start = billing_start.replace(day=21)
    
    if billing_start.month == 12:
        billing_end = billing_start.replace(year=billing_start.year + 1, month=1, day=20)
    else:
        billing_end = billing_start.replace(month=billing_start.month + 1, day=20)

    query = text("""
        SELECT 
            :msisdn as msisdn,
            :billing_month as billing_month,
            COUNT(DISTINCT DATE(data.effective_date)) as days_in_cycle,
            COALESCE(SUM(voice.duration_minutes), 0) as voice_minutes,
            COALESCE(COUNT(DISTINCT sms.id), 0) as sms_count,
            COALESCE(SUM(data.total_volume_bytes), 0) as data_bytes,
            COALESCE(SUM(data.total_volume_bytes) / 1073741824.0, 0) as data_gb
        FROM 
            (SELECT :msisdn as msisdn) sub
        LEFT JOIN cdr_voice voice 
            ON voice.msisdn = :msisdn 
            AND voice.effective_date >= :billing_start AND voice.effective_date <= :billing_end
        LEFT JOIN cdr_sms sms 
            ON sms.msisdn = :msisdn 
            AND sms.effective_date >= :billing_start AND sms.effective_date <= :billing_end
        LEFT JOIN cdr_data data 
            ON data.msisdn = :msisdn 
            AND data.effective_date >= :billing_start AND data.effective_date <= :billing_end
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {
                'msisdn': msisdn, 'billing_month': billing_month,
                'billing_start': billing_start, 'billing_end': billing_end
            })
            row = result.fetchone()
            if row:
                return {
                    'msisdn': row[0], 'billing_month': row[1], 'days_in_cycle': int(row[2]),
                    'voice_minutes': float(row[3]), 'sms_count': int(row[4]),
                    'data_bytes': float(row[5]), 'data_gb': float(row[6])
                }
    except Exception as e:
        logger.error(f"Error monthly aggregation for {msisdn}: {e}")
    return None

def calculate_usage_velocity(msisdn, days=7):
    """Calculate average daily usage over the past N days from the AGGREGATED table"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    query = text("""
        SELECT 
            msisdn,
            COUNT(DISTINCT usage_date) as active_days,
            AVG(voice_minutes) as avg_voice_minutes_per_day,
            AVG(sms_count) as avg_sms_per_day,
            AVG(data_bytes) as avg_data_bytes_per_day,
            AVG(data_bytes / 1073741824.0) as avg_data_gb_per_day,
            STDDEV(data_bytes / 1073741824.0) as stddev_data_gb
        FROM usage_daily_agg
        WHERE msisdn = :msisdn
        AND usage_date >= :start_date
        AND usage_date <= :end_date
        GROUP BY msisdn
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {'msisdn': msisdn, 'start_date': start_date, 'end_date': end_date})
            row = result.fetchone()
            if row:
                return {
                    'msisdn': row[0], 'lookback_days': days, 'active_days': int(row[1]),
                    'avg_voice_minutes_per_day': float(row[2]), 'avg_sms_per_day': float(row[3]),
                    'avg_data_bytes_per_day': float(row[4]), 'avg_data_gb_per_day': float(row[5]),
                    'stddev_data_gb': float(row[6]) if row[6] else 0.0
                }
    except Exception as e:
        logger.error(f"Error calculating velocity for {msisdn}: {e}")
    return None

def populate_daily_aggregates(start_date=None, end_date=None):
    """Populates usage_daily_agg with multi-event handling and ON CONFLICT logic"""
    if not start_date: start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date: end_date = datetime.now().strftime('%Y-%m-%d')
    
    query = text("""
        INSERT INTO usage_daily_agg (
            usage_date, msisdn, voice_minutes, sms_count, data_bytes,
            voice_events, sms_events, data_sessions
        )
        SELECT 
            usage_date, msisdn, 
            SUM(v_min), SUM(s_cnt), SUM(d_byt),
            SUM(v_evt), SUM(s_evt), SUM(d_ses)
        FROM (
            SELECT DATE(effective_date) as usage_date, msisdn, 
                   COALESCE(SUM(duration_minutes), 0) as v_min, 0 as s_cnt, 0 as d_byt,
                   COUNT(*) as v_evt, 0 as s_evt, 0 as d_ses
            FROM cdr_voice WHERE DATE(effective_date) BETWEEN :start_date AND :end_date
            GROUP BY 1, 2
            UNION ALL
            SELECT DATE(effective_date) as usage_date, msisdn, 
                   0, COUNT(*), 0, 0, COUNT(*), 0
            FROM cdr_sms WHERE DATE(effective_date) BETWEEN :start_date AND :end_date
            GROUP BY 1, 2
            UNION ALL
            SELECT DATE(effective_date) as usage_date, msisdn, 
                   0, 0, SUM(total_volume_bytes), 0, 0, COUNT(*)
            FROM cdr_data WHERE DATE(effective_date) BETWEEN :start_date AND :end_date
            GROUP BY 1, 2
        ) AS combined
        GROUP BY usage_date, msisdn
        ON CONFLICT (usage_date, msisdn) 
        DO UPDATE SET
            voice_minutes = EXCLUDED.voice_minutes,
            sms_count = EXCLUDED.sms_count,
            data_bytes = EXCLUDED.data_bytes,
            voice_events = EXCLUDED.voice_events,
            sms_events = EXCLUDED.sms_events,
            data_sessions = EXCLUDED.data_sessions,
            updated_at = NOW()
    """)
    
    try:
        with engine.begin() as conn:
            conn.execute(query, {'start_date': start_date, 'end_date': end_date})
            logger.info("Daily aggregates populated successfully.")
            return True
    except Exception as e:
        logger.error(f"Error populating aggregates: {e}")
        return False

def get_current_billing_cycle_dates():
    today = datetime.now().date()
    if today.day < 21:
        billing_start = (today.replace(day=1) - timedelta(days=1)).replace(day=21)
        billing_end = today.replace(day=20)
    else:
        billing_start = today.replace(day=21)
        # Advance to next month's 20th
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=20)
        billing_end = next_month
    return billing_start, billing_end

def get_subscriber_usage_summary(msisdn):
    billing_start, billing_end = get_current_billing_cycle_dates()
    monthly = aggregate_monthly_usage(msisdn, billing_start.strftime('%Y-%m-%d'))
    velocity = calculate_usage_velocity(msisdn, days=7)
    
    if monthly and velocity:
        return {
            'msisdn': msisdn,
            'billing_cycle': {'start': str(billing_start), 'end': str(billing_end)},
            'usage_mtd': {'voice_min': monthly['voice_minutes'], 'data_gb': monthly['data_gb']},
            'velocity': {'avg_gb_day': velocity['avg_data_gb_per_day']}
        }
    return None

if __name__ == "__main__":
    # Test block
    test_msisdn = "2026853028"
    logger.info("Starting Usage Aggregation Test Run")
    
    # 1. Populate tables
    populate_daily_aggregates("2026-01-01", "2026-02-10")
    
    # 2. Test functions
    summary = get_subscriber_usage_summary(test_msisdn)
    if summary:
        print("\n" + "="*50)
        print(f"PIPELINE TEST RESULTS FOR {test_msisdn}")
        print(f"Billing Cycle: {summary['billing_cycle']['start']} to {summary['billing_cycle']['end']}")
        print(f"MTD Usage:     {summary['usage_mtd']['data_gb']:.2f} GB")
        print(f"Daily Velocity: {summary['velocity']['avg_gb_day']:.4f} GB/day")
        print("="*50 + "\n")