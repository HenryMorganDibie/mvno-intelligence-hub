"""
Donation Matcher
The "Marketplace" logic: Bridges the gap between Donors and Recipients.
"""

from sqlalchemy import text
from config.database import engine
from config.logging_config import setup_logging
from src.optimization.recipient_finder import find_at_risk_subscribers
from decimal import Decimal

logger = setup_logging(__name__)

def execute_matching_cycle():
    """
    Finds people who need data and pulls from the community pool to save them.
    """
    logger.info("--- Starting Donation Matching Cycle ---")

    # 1. Get the current Community Pool (The 'Bank')
    # We look for active donors identified by the Threshold Calculator
    pool_query = text("""
        SELECT SUM(safe_donation_amount_gb) 
        FROM donation_thresholds 
        WHERE calculation_date = CURRENT_DATE 
          AND is_active = TRUE
    """)
    
    # 2. Identify the Recipients (The 'Need')
    recipients = find_at_risk_subscribers()
    
    if not recipients:
        logger.info("No subscribers currently at risk. Matching cycle complete.")
        return

    try:
        with engine.connect() as conn:
            # Handle Decimal vs Float issue immediately
            raw_pool = conn.execute(pool_query).scalar()
            available_pool = float(raw_pool) if raw_pool else 0.0
            
            logger.info(f"💰 Available Community Pool: {available_pool:.2f} GB")

            for recipient in recipients:
                if available_pool <= 0:
                    logger.warning("🚨 Community Pool exhausted! Remaining recipients will incur overages.")
                    break
                
                msisdn = recipient['msisdn']
                # Ensure shortfall is a float
                shortfall = float(recipient['shortfall_gb'])
                
                # Calculate the gift (we either cover the whole need or give what's left)
                gift_amount = min(available_pool, shortfall)
                
                if gift_amount > 0:
                    logger.info(f"🎁 MATCHED: Gifting {gift_amount:.2f} GB to {msisdn}")
                    
                    # 3. PERMANENT TRANSACTION RECORD
                    # This tells the billing engine: 'Do not charge overages for this amount'
                    transaction_query = text("""
                        INSERT INTO data_donations (
                            recipient_msisdn, 
                            amount_gb, 
                            transaction_date, 
                            status
                        ) VALUES (:msisdn, :amount, NOW(), 'COMPLETED')
                    """)
                    
                    conn.execute(transaction_query, {
                        'msisdn': msisdn,
                        'amount': gift_amount
                    })
                    
                    # Deduct from our temporary local pool counter
                    available_pool -= gift_amount
                
            # Commit the gifts (if using engine.begin() or autocommit is off)
            conn.commit() 
            logger.info("--- Matching Cycle Completed Successfully ---")

    except Exception as e:
        logger.error(f"Critical failure in matching cycle: {e}")

if __name__ == "__main__":
    execute_matching_cycle()