"""
Donation Matcher (Core Engine - Finalized)
Bridges the gap between Donors and Recipients with Fairness Caps,
Donor Attribution, and True Round-Robin Load Balancing.
"""

from collections import deque
from sqlalchemy import text
from config.database import engine
from config.logging_config import setup_logging
from src.optimization.recipient_finder import find_at_risk_subscribers

logger = setup_logging(__name__)

# CONFIGURATION
MAX_GIFT_GB = 2.0
HERO_SAFETY_BUFFER = 0.1


def execute_matching_cycle():
    logger.info("--- Starting PRODUCTION Donation Matching Cycle ---")

    hero_query = text("""
        SELECT msisdn, safe_donation_amount_gb
        FROM donation_thresholds
        WHERE calculation_date = CURRENT_DATE
          AND is_active = TRUE
          AND safe_donation_amount_gb > :buffer
        ORDER BY safe_donation_amount_gb DESC
    """)

    recipients = find_at_risk_subscribers()

    if not recipients:
        logger.info("✅ No subscribers at risk. Matching cycle complete.")
        return

    try:
        with engine.connect() as conn:
            hero_rows = conn.execute(hero_query, {"buffer": HERO_SAFETY_BUFFER}).fetchall()

            heroes = deque([{"msisdn": h[0], "balance": float(h[1])} for h in hero_rows])

            total_pool = sum(h['balance'] for h in heroes)
            logger.info(f"💰 Pool: {total_pool:.2f} GB | Heroes: {len(heroes)} | Needs: {len(recipients)}")

            for recipient in recipients:
                msisdn = recipient['msisdn']
                needed_amount = min(float(recipient['shortfall_gb']), MAX_GIFT_GB)

                matched = False
                attempts = 0
                while not matched and attempts < len(heroes):
                    hero = heroes[0]
                    attempts += 1

                    if hero['balance'] <= HERO_SAFETY_BUFFER:
                        heroes.popleft()
                        continue

                    gift = min(hero['balance'], needed_amount)

                    if gift > 0.01:
                        # Prevent duplicate donations for same donor/recipient today
                        check_query = text("""
                            SELECT COUNT(*) FROM data_donations
                            WHERE donor_msisdn = :donor
                            AND recipient_msisdn = :recipient
                            AND transaction_date::date = CURRENT_DATE
                        """)
                        already_matched = conn.execute(check_query, {
                            'donor': hero['msisdn'],
                            'recipient': msisdn
                        }).scalar()

                        if already_matched:
                            logger.info(f"⏭️ Skipping duplicate: {hero['msisdn']} -> {msisdn} (already matched today)")
                            matched = True
                            continue

                        logger.info(f"🎁 MATCH: {hero['msisdn']} -> {gift:.2f} GB -> {msisdn}")

                        transaction_query = text("""
                            INSERT INTO data_donations (
                                donor_msisdn, recipient_msisdn, amount_gb,
                                transaction_date, status
                            ) VALUES (:donor, :recipient, :amount, NOW(), 'COMPLETED')
                        """)

                        conn.execute(transaction_query, {
                            'donor': hero['msisdn'],
                            'recipient': msisdn,
                            'amount': gift
                        })

                        hero['balance'] -= gift
                        heroes.rotate(-1)
                        matched = True

                conn.commit()

            logger.info(f"--- Cycle Complete. {len(heroes)} Heroes still have capacity. ---")

    except Exception as e:
        logger.error(f"❌ Critical failure in matching cycle: {e}")


if __name__ == "__main__":
    execute_matching_cycle()
