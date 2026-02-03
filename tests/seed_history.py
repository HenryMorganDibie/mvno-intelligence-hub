import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import text
from config.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_subscriber_history(msisdn, days=14):
    """Generates 14 days of historical usage for a realistic Prophet forecast"""
    today = datetime.now().date()
    history_data = []
    
    # Generate a range of data points
    for i in range(days, 0, -1):
        usage_date = today - timedelta(days=i)
        
        # Random data: 0.5GB to 1.8GB to simulate a heavy user
        data_gb = np.random.uniform(0.5, 1.8)
        data_bytes = int(data_gb * 1073741824)
        
        history_data.append({
            'usage_date': usage_date,
            'msisdn': msisdn,
            'voice_minutes': np.random.randint(5, 45),
            'sms_count': np.random.randint(0, 10),
            'data_bytes': data_bytes,
            'voice_events': np.random.randint(2, 10),
            'sms_events': np.random.randint(0, 10),
            'data_sessions': np.random.randint(10, 50)
        })

    # Upsert query
    query = text("""
        INSERT INTO usage_daily_agg (
            usage_date, msisdn, voice_minutes, sms_count, data_bytes,
            voice_events, sms_events, data_sessions
        ) VALUES (
            :usage_date, :msisdn, :voice_minutes, :sms_count, :data_bytes,
            :voice_events, :sms_events, :data_sessions
        )
        ON CONFLICT (usage_date, msisdn) DO UPDATE SET
            data_bytes = EXCLUDED.data_bytes,
            updated_at = NOW()
    """)

    try:
        with engine.begin() as conn:
            for record in history_data:
                conn.execute(query, record)
        logger.info(f"✅ Successfully seeded {days} days of history for {msisdn}")
    except Exception as e:
        logger.error(f"❌ Failed to seed history: {e}")

if __name__ == "__main__":
    seed_subscriber_history("2026853028")