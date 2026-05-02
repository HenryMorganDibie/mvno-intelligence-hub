"""
Real-Time Usage Predictor
Shows current session usage and projects usage for the next 1-4 hours.
Lightweight — no Prophet training needed, uses recent session velocity.
"""

from datetime import datetime, timedelta
from sqlalchemy import text

from config.logging_config import setup_logging
from config.database import engine

logger = setup_logging(__name__)


def get_realtime_usage(msisdn):
    """
    Returns current day usage and velocity based on recent sessions.
    Designed to update every 15 minutes as new CDR data arrives.
    """
    now = datetime.now()
    today = now.date()
    one_hour_ago = now - timedelta(hours=1)
    four_hours_ago = now - timedelta(hours=4)

    query = text("""
        SELECT
            -- Today's total usage
            COALESCE(SUM(CASE WHEN usage_time::date = :today
                THEN bytes_up + bytes_down ELSE 0 END), 0) / 1073741824.0 as today_gb,

            -- Last 1 hour usage
            COALESCE(SUM(CASE WHEN usage_time >= :one_hour_ago
                THEN bytes_up + bytes_down ELSE 0 END), 0) / 1073741824.0 as last_1h_gb,

            -- Last 4 hours usage
            COALESCE(SUM(CASE WHEN usage_time >= :four_hours_ago
                THEN bytes_up + bytes_down ELSE 0 END), 0) / 1073741824.0 as last_4h_gb,

            -- Session count today
            COUNT(CASE WHEN usage_time::date = :today THEN 1 END) as sessions_today,

            -- Last session time
            MAX(usage_time) as last_seen

        FROM daily_usage
        WHERE msisdn = :msisdn
        AND usage_time >= :four_hours_ago
    """)

    try:
        with engine.connect() as conn:
            row = conn.execute(query, {
                'msisdn': msisdn,
                'today': today,
                'one_hour_ago': one_hour_ago,
                'four_hours_ago': four_hours_ago
            }).fetchone()

            if not row:
                return None

            today_gb = float(row[0])
            last_1h_gb = float(row[1])
            last_4h_gb = float(row[2])
            sessions_today = int(row[3])
            last_seen = row[4]

            # Velocity: GB per hour based on last 4 hours
            velocity_gb_per_hour = last_4h_gb / 4.0 if last_4h_gb > 0 else 0

            # Project next 1, 2, 4 hours
            projected_1h_gb = today_gb + (velocity_gb_per_hour * 1)
            projected_2h_gb = today_gb + (velocity_gb_per_hour * 2)
            projected_4h_gb = today_gb + (velocity_gb_per_hour * 4)

            return {
                'msisdn': str(msisdn),
                'as_of': now.isoformat(),
                'today_gb': round(today_gb, 4),
                'last_1h_gb': round(last_1h_gb, 4),
                'last_4h_gb': round(last_4h_gb, 4),
                'velocity_gb_per_hour': round(velocity_gb_per_hour, 4),
                'projected_1h_gb': round(projected_1h_gb, 4),
                'projected_2h_gb': round(projected_2h_gb, 4),
                'projected_4h_gb': round(projected_4h_gb, 4),
                'sessions_today': sessions_today,
                'last_seen': last_seen.isoformat() if last_seen else None
            }

    except Exception as e:
        logger.error(f"Error getting real-time usage for {msisdn}: {e}")
        return None


def get_realtime_usage_from_dsr(msisdn):
    """
    Fallback: Get today's usage from daily_subscriber_reports if CDR is sparse.
    DSR is more reliable for total daily bytes.
    """
    today = datetime.now().date()

    query = text("""
        SELECT
            usage_date,
            COALESCE(data_bytes, 0) / 1073741824.0 as data_gb,
            COALESCE(voice_minutes, 0) as voice_minutes,
            COALESCE(sms_units, 0) as sms_units,
            subscriber_state,
            active_status
        FROM daily_subscriber_reports
        WHERE msisdn = :msisdn
        AND usage_date >= :start_date
        ORDER BY usage_date DESC
        LIMIT 7
    """)

    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {
                'msisdn': msisdn,
                'start_date': today - timedelta(days=7)
            }).fetchall()

            if not rows:
                return None

            latest = rows[0]
            recent_days = [
                {
                    'date': str(row[0]),
                    'data_gb': round(float(row[1]), 4),
                    'voice_minutes': float(row[2]),
                    'sms_units': float(row[3])
                }
                for row in rows
            ]

            avg_daily_gb = sum(d['data_gb'] for d in recent_days) / len(recent_days)

            return {
                'msisdn': str(msisdn),
                'as_of': datetime.now().isoformat(),
                'latest_date': str(latest[0]),
                'latest_data_gb': round(float(latest[1]), 4),
                'subscriber_state': latest[4],
                'active_status': int(latest[5]) if latest[5] is not None else None,
                'avg_daily_gb_7d': round(avg_daily_gb, 4),
                'recent_days': recent_days
            }

    except Exception as e:
        logger.error(f"Error getting DSR real-time usage for {msisdn}: {e}")
        return None


def get_full_realtime_profile(msisdn):
    """
    Combined real-time profile — CDR velocity + DSR snapshot.
    This is what the API serves to the customer app.
    """
    cdr_data = get_realtime_usage(msisdn)
    dsr_data = get_realtime_usage_from_dsr(msisdn)

    return {
        'msisdn': str(msisdn),
        'as_of': datetime.now().isoformat(),
        'cdr_realtime': cdr_data,
        'dsr_snapshot': dsr_data
    }


if __name__ == "__main__":
    test_msisdn = "4042778501"
    logger.info(f"Testing Real-Time Predictor for {test_msisdn}")

    profile = get_full_realtime_profile(test_msisdn)

    print("\n" + "="*50)
    print(f"REAL-TIME PROFILE: {test_msisdn}")
    if profile['cdr_realtime']:
        rt = profile['cdr_realtime']
        print(f"Today so far:     {rt['today_gb']:.4f} GB")
        print(f"Last 1 hour:      {rt['last_1h_gb']:.4f} GB")
        print(f"Velocity:         {rt['velocity_gb_per_hour']:.4f} GB/hr")
        print(f"Projected +1hr:   {rt['projected_1h_gb']:.4f} GB")
        print(f"Projected +4hr:   {rt['projected_4h_gb']:.4f} GB")
    if profile['dsr_snapshot']:
        dsr = profile['dsr_snapshot']
        print(f"Latest DSR date:  {dsr['latest_date']}")
        print(f"Latest DSR GB:    {dsr['latest_data_gb']:.4f} GB")
        print(f"7-day avg:        {dsr['avg_daily_gb_7d']:.4f} GB/day")
    print("="*50 + "\n")
