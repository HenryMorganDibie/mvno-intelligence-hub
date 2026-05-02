"""
Donation Threshold Calculator
Calculates safe data donation amounts for subscribers to prevent overages.
"""

from datetime import datetime
from sqlalchemy import text

from config.database import engine
from config.logging_config import setup_logging

logger = setup_logging(__name__)


def calculate_safe_donation(
    allocated_capacity_gb,
    predicted_usage_gb,
    confidence_upper_gb,
    safety_factor=1.2
):
    """
    Formula: Safe Amount = Allocated - Predicted - (Uncertainty * Safety Factor)
    """
    uncertainty_gb = confidence_upper_gb - predicted_usage_gb
    confidence_buffer_gb = uncertainty_gb * safety_factor
    safe_donation_gb = allocated_capacity_gb - predicted_usage_gb - confidence_buffer_gb
    safe_donation_gb = max(0, round(safe_donation_gb, 2))
    can_donate = safe_donation_gb >= 0.5
    utilization_pct = (predicted_usage_gb / allocated_capacity_gb) * 100 if allocated_capacity_gb > 0 else 0

    return {
        'allocated_capacity_gb': round(allocated_capacity_gb, 2),
        'predicted_usage_gb': round(predicted_usage_gb, 2),
        'confidence_upper_gb': round(confidence_upper_gb, 2),
        'confidence_buffer_gb': round(confidence_buffer_gb, 2),
        'safe_donation_gb': safe_donation_gb,
        'can_donate': can_donate,
        'utilization_pct': round(utilization_pct, 1),
        'safety_factor': safety_factor,
        'calculated_at': datetime.now().isoformat()
    }


def calculate_donation_for_subscriber(msisdn):
    """Fetches DB state and runs the calculation logic"""
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    b_month = billing_start.strftime('%Y-%m')

    query = text("""
        SELECT
            pt.data_cap_gb, pt.tier_name,
            p.predicted_data_gb, p.confidence_upper_gb, p.current_usage_gb
        FROM pool_assignments pa
        JOIN pool_tiers pt ON pa.tier_id = pt.tier_id
        JOIN predictions_current_month p ON pa.msisdn = p.msisdn
            AND pa.billing_month = p.billing_month
        WHERE pa.msisdn = :msisdn
          AND pa.billing_month = :billing_month
        ORDER BY pa.assigned_date DESC, p.prediction_date DESC
        LIMIT 1
    """)

    try:
        with engine.connect() as conn:
            row = conn.execute(query, {'msisdn': msisdn, 'billing_month': b_month}).fetchone()

            if not row:
                logger.warning(f"Insufficient data for donation calc: {msisdn}")
                return None

            alloc_gb, t_name, pred_gb, conf_up, curr_gb = row

            res = calculate_safe_donation(float(alloc_gb), float(pred_gb), float(conf_up))
            res.update({'msisdn': msisdn, 'tier_name': t_name, 'current_usage_gb': round(float(curr_gb), 2)})
            return res

    except Exception as e:
        logger.error(f"Donation calculation failed for {msisdn}: {e}")
        return None


def save_donation_threshold_to_db(donation):
    """Updates the donor dashboard values"""
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()

    query = text("""
        INSERT INTO donation_thresholds (
            msisdn, billing_month, calculation_date,
            allocated_data_gb, predicted_usage_gb,
            confidence_buffer_gb, safe_donation_amount_gb, is_active
        ) VALUES (
            :msisdn, :billing_month, NOW(),
            :alloc, :pred, :buffer, :safe, :active
        )
        ON CONFLICT (msisdn, billing_month, calculation_date)
        DO UPDATE SET
            safe_donation_amount_gb = EXCLUDED.safe_donation_amount_gb,
            is_active = EXCLUDED.is_active
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, {
                'msisdn': donation['msisdn'],
                'billing_month': billing_start.strftime('%Y-%m'),
                'alloc': donation['allocated_capacity_gb'],
                'pred': donation['predicted_usage_gb'],
                'buffer': donation['confidence_buffer_gb'],
                'safe': donation['safe_donation_gb'],
                'active': donation['can_donate']
            })
        return True
    except Exception as e:
        logger.error(f"Failed to save threshold: {e}")
        return False


if __name__ == "__main__":
    test_msisdn = "4042778501"
    print(f"--- Donation Analysis: {test_msisdn} ---")

    analysis = calculate_donation_for_subscriber(test_msisdn)
    if analysis:
        print(f"Tier: {analysis['tier_name']} ({analysis['allocated_capacity_gb']}GB)")
        print(f"Safety Buffer Reserved: {analysis['confidence_buffer_gb']} GB")
        print(f"Available to Donate:   {analysis['safe_donation_gb']} GB")

        if analysis['can_donate']:
            print("\n✅ STATUS: ELIGIBLE TO DONATE")
            save_donation_threshold_to_db(analysis)
        else:
            print("\n❌ STATUS: NOT ELIGIBLE (Usage too high/uncertain)")
