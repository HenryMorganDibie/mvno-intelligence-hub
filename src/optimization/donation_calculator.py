"""
Donation Threshold Calculator
Calculates safe data donation amounts for subscribers
"""

from datetime import datetime
from sqlalchemy import text
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database connection
from config.database import engine


def calculate_safe_donation(
    allocated_capacity_gb,
    predicted_usage_gb,
    confidence_upper_gb,
    safety_factor=1.2
):
    """
    Calculate how much data a subscriber can safely donate
    
    Formula:
        Safe Amount = Allocated - Predicted - (Confidence Buffer × Safety Factor)
    
    Args:
        allocated_capacity_gb (float): Tier capacity assigned to user
        predicted_usage_gb (float): Predicted total usage
        confidence_upper_gb (float): Upper confidence bound
        safety_factor (float): Safety multiplier (default 1.2 = 20% buffer)
    
    Returns:
        dict: Donation calculation details
    """
    # Calculate confidence buffer
    confidence_buffer_gb = (confidence_upper_gb - predicted_usage_gb) * safety_factor
    
    # Calculate safe donation amount
    safe_donation_gb = allocated_capacity_gb - predicted_usage_gb - confidence_buffer_gb
    
    # Never allow negative donations
    safe_donation_gb = max(0, safe_donation_gb)
    
    # Determine donation eligibility
    can_donate = safe_donation_gb >= 0.5  # Minimum 0.5 GB to donate
    
    # Calculate utilization
    utilization_pct = (predicted_usage_gb / allocated_capacity_gb) * 100 if allocated_capacity_gb > 0 else 0
    
    result = {
        'allocated_capacity_gb': round(allocated_capacity_gb, 2),
        'predicted_usage_gb': round(predicted_usage_gb, 2),
        'confidence_upper_gb': round(confidence_upper_gb, 2),
        'confidence_buffer_gb': round(confidence_buffer_gb, 2),
        'safe_donation_gb': round(safe_donation_gb, 2),
        'can_donate': can_donate,
        'utilization_pct': round(utilization_pct, 1),
        'safety_factor': safety_factor,
        'calculated_at': datetime.now().isoformat()
    }
    
    logger.info(f"Safe donation calculated: {safe_donation_gb:.2f} GB "
               f"(allocated={allocated_capacity_gb}, predicted={predicted_usage_gb})")
    
    return result


def calculate_donation_for_subscriber(msisdn):
    """
    Complete donation calculation workflow for a subscriber
    
    Args:
        msisdn (str): Subscriber phone number
    
    Returns:
        dict: Donation threshold details
    """
    # Get subscriber's current tier assignment
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    tier_query = text("""
        SELECT 
            pa.tier_id,
            pt.data_cap_gb,
            pt.tier_name
        FROM pool_assignments pa
        JOIN pool_tiers pt ON pa.tier_id = pt.tier_id
        WHERE pa.msisdn = :msisdn
        AND pa.billing_month = :billing_month
        ORDER BY pa.assigned_date DESC
        LIMIT 1
    """)
    
    # Get current prediction
    prediction_query = text("""
        SELECT 
            predicted_data_gb,
            confidence_upper_gb,
            current_usage_gb
        FROM predictions_current_month
        WHERE msisdn = :msisdn
        AND billing_month = :billing_month
        ORDER BY prediction_date DESC
        LIMIT 1
    """)
    
    try:
        with engine.connect() as conn:
            # Get tier info
            tier_result = conn.execute(tier_query, {
                'msisdn': msisdn,
                'billing_month': billing_start.strftime('%Y-%m-%d')
            })
            tier_row = tier_result.fetchone()
            
            if not tier_row:
                logger.warning(f"No tier assignment found for {msisdn}")
                return None
            
            tier_id, allocated_gb, tier_name = tier_row
            
            # Get prediction
            pred_result = conn.execute(prediction_query, {
                'msisdn': msisdn,
                'billing_month': billing_start.strftime('%Y-%m-%d')
            })
            pred_row = pred_result.fetchone()
            
            if not pred_row:
                logger.warning(f"No prediction found for {msisdn}")
                return None
            
            predicted_gb, confidence_upper_gb, current_usage_gb = pred_row
        
        # Calculate safe donation
        donation = calculate_safe_donation(
            allocated_capacity_gb=float(allocated_gb),
            predicted_usage_gb=float(predicted_gb),
            confidence_upper_gb=float(confidence_upper_gb),
            safety_factor=1.2
        )
        
        # Add subscriber and tier info
        donation['msisdn'] = msisdn
        donation['tier_id'] = tier_id
        donation['tier_name'] = tier_name
        donation['current_usage_gb'] = round(float(current_usage_gb), 2)
        
        return donation
        
    except Exception as e:
        logger.error(f"Error calculating donation for {msisdn}: {e}")
        return None


def save_donation_threshold_to_db(donation):
    """
    Save donation threshold to database
    
    Args:
        donation (dict): Donation calculation details
    
    Returns:
        bool: True if successful
    """
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    query = text("""
        INSERT INTO donation_thresholds (
            msisdn, billing_month, calculation_date,
            allocated_data_gb, predicted_usage_gb,
            confidence_buffer_gb, safe_donation_amount_gb,
            is_active
        ) VALUES (
            :msisdn, :billing_month, :calculation_date,
            :allocated_data_gb, :predicted_usage_gb,
            :confidence_buffer_gb, :safe_donation_amount_gb,
            :is_active
        )
        ON CONFLICT (msisdn, billing_month, calculation_date)
        DO UPDATE SET
            allocated_data_gb = EXCLUDED.allocated_data_gb,
            predicted_usage_gb = EXCLUDED.predicted_usage_gb,
            confidence_buffer_gb = EXCLUDED.confidence_buffer_gb,
            safe_donation_amount_gb = EXCLUDED.safe_donation_amount_gb,
            is_active = EXCLUDED.is_active,
            created_at = NOW()
    """)
    
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                'msisdn': donation['msisdn'],
                'billing_month': billing_start.strftime('%Y-%m-%d'),
                'calculation_date': datetime.now().date(),
                'allocated_data_gb': donation['allocated_capacity_gb'],
                'predicted_usage_gb': donation['predicted_usage_gb'],
                'confidence_buffer_gb': donation['confidence_buffer_gb'],
                'safe_donation_amount_gb': donation['safe_donation_gb'],
                'is_active': donation['can_donate']
            })
        logger.info(f"Saved donation threshold for {donation['msisdn']}")
        return True
    except Exception as e:
        logger.error(f"Error saving donation threshold: {e}")
        return False


def record_donation(donor_msisdn, amount_gb, recipient_msisdn=None, reward_points=None):
    """
    Record an actual data donation
    
    Args:
        donor_msisdn (str): Donor's phone number
        amount_gb (float): Amount donated in GB
        recipient_msisdn (str, optional): Recipient's phone number
        reward_points (int, optional): Reward points earned (default: 1 point per GB)
    
    Returns:
        dict: Donation record
    """
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    # Calculate reward points (1 point per GB if not specified)
    if reward_points is None:
        reward_points = int(amount_gb)
    
    query = text("""
        INSERT INTO donations (
            donor_msisdn, recipient_msisdn, donation_amount_gb,
            billing_month, status, reward_points
        ) VALUES (
            :donor_msisdn, :recipient_msisdn, :donation_amount_gb,
            :billing_month, :status, :reward_points
        )
        RETURNING donation_id
    """)
    
    try:
        with engine.begin() as conn:
            result = conn.execute(query, {
                'donor_msisdn': donor_msisdn,
                'recipient_msisdn': recipient_msisdn,
                'donation_amount_gb': amount_gb,
                'billing_month': billing_start.strftime('%Y-%m-%d'),
                'status': 'completed',
                'reward_points': reward_points
            })
            donation_id = result.fetchone()[0]
        
        # Recalculate donor's safe donation amount (reduced after donation)
        updated_donation = calculate_donation_for_subscriber(donor_msisdn)
        if updated_donation:
            save_donation_threshold_to_db(updated_donation)
        
        logger.info(f"Recorded donation: {donor_msisdn} donated {amount_gb} GB, "
                   f"earned {reward_points} points")
        
        return {
            'donation_id': donation_id,
            'donor_msisdn': donor_msisdn,
            'recipient_msisdn': recipient_msisdn,
            'amount_gb': amount_gb,
            'reward_points': reward_points,
            'status': 'completed',
            'new_safe_donation_gb': updated_donation['safe_donation_gb'] if updated_donation else 0
        }
        
    except Exception as e:
        logger.error(f"Error recording donation: {e}")
        return None


def batch_calculate_donation_thresholds():
    """
    Calculate donation thresholds for all active subscribers
    
    Returns:
        dict: Calculation summary
    """
    # Get all active subscribers
    query = text("""
        SELECT DISTINCT msisdn
        FROM subscribers
        WHERE current_status = 'ACTIVE'
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            msisdns = [row[0] for row in result]
        
        logger.info(f"Calculating donation thresholds for {len(msisdns)} subscribers")
        
        summary = {
            'total_subscribers': len(msisdns),
            'can_donate': 0,
            'cannot_donate': 0,
            'total_donatable_gb': 0,
            'avg_safe_donation_gb': 0
        }
        
        donatable_amounts = []
        
        for msisdn in msisdns:
            try:
                donation = calculate_donation_for_subscriber(msisdn)
                if donation:
                    if save_donation_threshold_to_db(donation):
                        if donation['can_donate']:
                            summary['can_donate'] += 1
                            summary['total_donatable_gb'] += donation['safe_donation_gb']
                            donatable_amounts.append(donation['safe_donation_gb'])
                        else:
                            summary['cannot_donate'] += 1
            except Exception as e:
                logger.error(f"Error processing {msisdn}: {e}")
                continue
        
        if donatable_amounts:
            summary['avg_safe_donation_gb'] = round(
                sum(donatable_amounts) / len(donatable_amounts), 2
            )
        
        logger.info(f"Donation calculation complete: {summary['can_donate']} can donate, "
                   f"{summary['total_donatable_gb']:.2f} GB total available")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in batch donation calculation: {e}")
        return None


# Test function
if __name__ == "__main__":
    print("Testing Donation Calculator\n")
    print("=" * 50)
    
    # Test subscriber
    test_msisdn = "2026853028"
    
    print(f"\n1. Calculating donation threshold for {test_msisdn}...")
    donation = calculate_donation_for_subscriber(test_msisdn)
    
    if donation:
        print("\n✅ Donation Calculation:")
        print(f"   MSISDN: {donation['msisdn']}")
        print(f"   Current Tier: {donation['tier_name']}")
        print(f"   Allocated Capacity: {donation['allocated_capacity_gb']} GB")
        print(f"   Current Usage: {donation['current_usage_gb']} GB")
        print(f"   Predicted Usage: {donation['predicted_usage_gb']} GB")
        print(f"   Confidence Buffer: {donation['confidence_buffer_gb']} GB")
        print(f"   Safe to Donate: {donation['safe_donation_gb']} GB")
        print(f"   Can Donate: {'✅ Yes' if donation['can_donate'] else '❌ No'}")
        print(f"   Utilization: {donation['utilization_pct']}%")
        
        # Save to database
        if save_donation_threshold_to_db(donation):
            print("\n✅ Threshold saved to database")
        
        # Test recording a donation
        if donation['can_donate'] and donation['safe_donation_gb'] >= 1.0:
            print(f"\n2. Recording test donation of 1 GB...")
            donation_record = record_donation(
                donor_msisdn=test_msisdn,
                amount_gb=1.0,
                recipient_msisdn="2024828332"
            )
            if donation_record:
                print("\n✅ Donation Recorded:")
                print(f"   Donation ID: {donation_record['donation_id']}")
                print(f"   Amount: {donation_record['amount_gb']} GB")
                print(f"   Reward Points: {donation_record['reward_points']}")
                print(f"   New Safe Donation: {donation_record['new_safe_donation_gb']} GB")
    else:
        print("\n❌ Calculation failed")
    
    print("\n" + "=" * 50)