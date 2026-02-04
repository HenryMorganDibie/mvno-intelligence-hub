"""
Batch Processor
Runs the full Intelligence Pipeline for all active subscribers.
"""

from sqlalchemy import text
from config.database import engine
from config.logging_config import setup_logging
from main import run_subscriber_pipeline

logger = setup_logging(__name__)

def run_fleet_optimization():
    # 1. Get all active subscribers
    query = text("SELECT msisdn FROM subscribers WHERE current_status = 'ACTIVE'")
    
    try:
        with engine.connect() as conn:
            subscribers = [row[0] for row in conn.execute(query)]
        
        logger.info(f"🚀 Starting Batch Processing for {len(subscribers)} subscribers...")
        
        success_count = 0
        for msisdn in subscribers:
            if run_subscriber_pipeline(msisdn):
                success_count += 1
        
        logger.info(f"✅ Batch Complete: {success_count}/{len(subscribers)} subscribers updated.")
        
        # 2. Show the "Community Power" (Total Donatable Data)
        report_query = text("""
            SELECT SUM(safe_donation_amount_gb) 
            FROM donation_thresholds 
            WHERE billing_month = (SELECT MAX(billing_month) FROM donation_thresholds)
            AND calculation_date = CURRENT_DATE
        """)
        
        with engine.connect() as conn:
            total_pool = conn.execute(report_query).scalar() or 0
            logger.info(f"📊 Total Community Data Pool: {total_pool:.2f} GB available for donation.")

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")

if __name__ == "__main__":
    run_fleet_optimization()