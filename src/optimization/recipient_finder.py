"""
Recipient Finder
Identifies subscribers trending toward overages who need data donations.
"""

from sqlalchemy import text
from config.database import engine
from config.logging_config import setup_logging

logger = setup_logging(__name__)

def find_at_risk_subscribers(min_shortfall_gb=0.1):
    """
    Finds ACTIVE subscribers whose predicted usage exceeds their current tier.
    Uses DISTINCT ON to ensure only the most recent prediction per user is analyzed.
    """
    query = text("""
        SELECT DISTINCT ON (p.msisdn)
            p.msisdn,
            p.predicted_data_gb,
            pa.tier_id,
            pt.tier_name,
            pt.data_cap_gb as allocated_gb,
            (p.predicted_data_gb - pt.data_cap_gb) as shortfall_gb
        FROM predictions_current_month p
        JOIN pool_assignments pa ON p.msisdn = pa.msisdn 
            AND p.billing_month = pa.billing_month
        JOIN pool_tiers pt ON pa.tier_id = pt.tier_id
        WHERE p.predicted_data_gb > pt.data_cap_gb
          AND p.prediction_date >= CURRENT_DATE - INTERVAL '1 day'
        ORDER BY p.msisdn, p.prediction_date DESC
    """)

    try:
        with engine.connect() as conn:
            results = conn.execute(query).fetchall()
            
        recipients = []
        for row in results:
            # Filtering out tiny shortfalls that aren't worth a transaction
            shortfall = round(float(row.shortfall_gb), 2)
            if shortfall >= min_shortfall_gb:
                recipients.append({
                    'msisdn': row.msisdn,
                    'predicted_gb': float(row.predicted_data_gb),
                    'tier_name': row.tier_name,
                    'allocated_gb': float(row.allocated_gb),
                    'shortfall_gb': shortfall
                })
            
        logger.info(f"Found {len(recipients)} subscribers at risk of overage.")
        return recipients

    except Exception as e:
        logger.error(f"Error finding recipients: {e}")
        return []

if __name__ == "__main__":
    print("--- 🚨 Overage Risk Report (Potential Recipients) ---")
    risky_users = find_at_risk_subscribers()
    for user in risky_users:
        print(f"MSISDN: {user['msisdn']} | Shortfall: {user['shortfall_gb']}GB (Needs Donation)")