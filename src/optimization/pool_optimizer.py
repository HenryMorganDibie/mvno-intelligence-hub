"""
Pool Optimization Engine
Assigns subscribers to optimal data pool tiers to minimize costs
"""

import os
from datetime import datetime
from sqlalchemy import text
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database connection
from config.database import engine

# Tier pricing structure (from Marvin's pricing table)
TIER_PRICING = {
    'PPP1': {
        'tier_id': 1,
        'tier_name': '1GB Pool',
        'cap_mb': 1000,
        'cap_gb': 1.0,
        'cost': 3.95,
        'overage_per_mb': 0.0045,
        'overage_per_gb': 4.50
    },
    'PPP2': {
        'tier_id': 2,
        'tier_name': '5GB Pool',
        'cap_mb': 5000,
        'cap_gb': 5.0,
        'cost': 12.00,
        'overage_per_mb': 0.0040,
        'overage_per_gb': 4.00
    },
    'PPP3': {
        'tier_id': 3,
        'tier_name': '10GB Pool',
        'cap_mb': 10000,
        'cap_gb': 10.0,
        'cost': 19.00,
        'overage_per_mb': 0.0035,
        'overage_per_gb': 3.50
    },
    'PPP4': {
        'tier_id': 4,
        'tier_name': '15GB Pool',
        'cap_mb': 15000,
        'cap_gb': 15.0,
        'cost': 24.50,
        'overage_per_mb': 0.0025,
        'overage_per_gb': 2.50
    },
    'PPP5': {
        'tier_id': 5,
        'tier_name': '30GB Pool',
        'cap_mb': 30000,
        'cap_gb': 30.0,
        'cost': 45.00,
        'overage_per_mb': 0.00200,
        'overage_per_gb': 2.00
    },
    'PPP6': {
        'tier_id': 6,
        'tier_name': '40GB Pool',
        'cap_mb': 40000,
        'cap_gb': 40.0,
        'cost': 58.00,
        'overage_per_mb': 0.00180,
        'overage_per_gb': 1.80
    }
}


def assign_optimal_tier(predicted_usage_gb, confidence_upper_gb, safety_buffer=0.10):
    """
    Assign subscriber to cheapest tier that fits predicted usage
    
    Args:
        predicted_usage_gb (float): Predicted total usage for billing cycle
        confidence_upper_gb (float): Upper bound of confidence interval
        safety_buffer (float): Additional safety margin (default 10%)
    
    Returns:
        dict: Optimal tier assignment
    """
    # Calculate required capacity with safety buffer
    required_capacity_gb = confidence_upper_gb * (1 + safety_buffer)
    
    # Find cheapest tier that fits
    for tier_code, tier_info in sorted(TIER_PRICING.items(), key=lambda x: x[1]['cost']):
        if tier_info['cap_gb'] >= required_capacity_gb:
            result = {
                'tier_code': tier_code,
                'tier_id': tier_info['tier_id'],
                'tier_name': tier_info['tier_name'],
                'tier_cost': tier_info['cost'],
                'tier_cap_gb': tier_info['cap_gb'],
                'predicted_usage_gb': round(predicted_usage_gb, 2),
                'confidence_upper_gb': round(confidence_upper_gb, 2),
                'required_capacity_gb': round(required_capacity_gb, 2),
                'headroom_gb': round(tier_info['cap_gb'] - required_capacity_gb, 2),
                'overage_risk': 'LOW' if required_capacity_gb < tier_info['cap_gb'] * 0.9 else 'MEDIUM',
                'reason': 'optimal_fit'
            }
            
            logger.info(f"Assigned to {tier_code}: predicted={predicted_usage_gb:.2f}GB, "
                       f"required={required_capacity_gb:.2f}GB, cap={tier_info['cap_gb']}GB")
            return result
    
    # If exceeds all tiers, assign to largest tier and flag for review
    largest_tier = TIER_PRICING['PPP6']
    result = {
        'tier_code': 'PPP6',
        'tier_id': largest_tier['tier_id'],
        'tier_name': largest_tier['tier_name'],
        'tier_cost': largest_tier['cost'],
        'tier_cap_gb': largest_tier['cap_gb'],
        'predicted_usage_gb': round(predicted_usage_gb, 2),
        'confidence_upper_gb': round(confidence_upper_gb, 2),
        'required_capacity_gb': round(required_capacity_gb, 2),
        'headroom_gb': round(largest_tier['cap_gb'] - required_capacity_gb, 2),
        'overage_risk': 'HIGH',
        'reason': 'exceeds_max_tier'
    }
    
    logger.warning(f"Subscriber exceeds max tier: predicted={predicted_usage_gb:.2f}GB, "
                  f"required={required_capacity_gb:.2f}GB")
    return result


def calculate_cost_comparison(predicted_usage_gb, confidence_upper_gb):
    """
    Calculate cost for each tier to show optimization savings
    
    Args:
        predicted_usage_gb (float): Predicted usage
        confidence_upper_gb (float): Upper confidence bound
    
    Returns:
        list: Cost breakdown for each tier
    """
    results = []
    
    for tier_code, tier_info in TIER_PRICING.items():
        # Base tier cost
        base_cost = tier_info['cost']
        
        # Calculate overage if predicted usage exceeds cap
        if confidence_upper_gb > tier_info['cap_gb']:
            overage_gb = confidence_upper_gb - tier_info['cap_gb']
            overage_cost = overage_gb * tier_info['overage_per_gb']
            total_cost = base_cost + overage_cost
            will_exceed = True
        else:
            overage_cost = 0
            total_cost = base_cost
            will_exceed = False
        
        results.append({
            'tier_code': tier_code,
            'tier_name': tier_info['tier_name'],
            'tier_cap_gb': tier_info['cap_gb'],
            'base_cost': base_cost,
            'overage_cost': round(overage_cost, 2),
            'total_cost': round(total_cost, 2),
            'will_exceed': will_exceed
        })
    
    return sorted(results, key=lambda x: x['total_cost'])


def optimize_subscriber_assignment(msisdn, force_retrain=False):
    """
    Complete optimization workflow for a single subscriber
    
    Args:
        msisdn (str): Subscriber phone number
        force_retrain (bool): Force model retraining
    
    Returns:
        dict: Optimization result
    """
    # Get prediction
    from src.models.current_month_predictor import predict_for_subscriber
    
    prediction = predict_for_subscriber(msisdn, retrain=force_retrain)
    if not prediction:
        logger.error(f"Could not get prediction for {msisdn}")
        return None
    
    # Assign optimal tier
    assignment = assign_optimal_tier(
        prediction['predicted_total_gb'],
        prediction['confidence_upper_gb'],
        safety_buffer=0.10  # 10% safety margin
    )
    
    # Get cost comparison
    cost_breakdown = calculate_cost_comparison(
        prediction['predicted_total_gb'],
        prediction['confidence_upper_gb']
    )
    
    result = {
        'msisdn': msisdn,
        'prediction': prediction,
        'assignment': assignment,
        'cost_breakdown': cost_breakdown,
        'optimized_at': datetime.now().isoformat()
    }
    
    return result


def save_pool_assignment_to_db(msisdn, assignment, previous_tier_id=None):
    """
    Save pool assignment to database
    
    Args:
        msisdn (str): Subscriber phone number
        assignment (dict): Assignment details
        previous_tier_id (int): Previous tier ID (if moving)
    
    Returns:
        bool: True if successful
    """
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    query = text("""
        INSERT INTO pool_assignments (
            msisdn, tier_id, billing_month, reason, previous_tier_id
        ) VALUES (
            :msisdn, :tier_id, :billing_month, :reason, :previous_tier_id
        )
    """)
    
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                'msisdn': msisdn,
                'tier_id': assignment['tier_id'],
                'billing_month': billing_start.strftime('%Y-%m-%d'),
                'reason': assignment['reason'],
                'previous_tier_id': previous_tier_id
            })
        logger.info(f"Saved pool assignment for {msisdn}: Tier {assignment['tier_id']}")
        return True
    except Exception as e:
        logger.error(f"Error saving pool assignment: {e}")
        return False


def batch_optimize_all_subscribers():
    """
    Run pool optimization for all active subscribers
    
    Returns:
        dict: Optimization summary
    """
    # Get all active subscribers with current tier
    query = text("""
        SELECT 
            s.msisdn,
            pa.tier_id as current_tier_id
        FROM subscribers s
        LEFT JOIN LATERAL (
            SELECT tier_id 
            FROM pool_assignments 
            WHERE msisdn = s.msisdn 
            ORDER BY assigned_date DESC 
            LIMIT 1
        ) pa ON TRUE
        WHERE s.current_status = 'ACTIVE'
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            subscribers = [{'msisdn': row[0], 'current_tier': row[1]} for row in result]
        
        logger.info(f"Optimizing pool assignments for {len(subscribers)} subscribers")
        
        summary = {
            'total_subscribers': len(subscribers),
            'successful_assignments': 0,
            'tier_moves': 0,
            'tier_distribution': {},
            'total_cost': 0,
            'estimated_savings': 0
        }
        
        # Baseline cost (everyone in max tier)
        baseline_cost = len(subscribers) * TIER_PRICING['PPP6']['cost']
        
        for sub in subscribers:
            try:
                # Optimize assignment
                optimization = optimize_subscriber_assignment(sub['msisdn'])
                if not optimization:
                    continue
                
                assignment = optimization['assignment']
                
                # Save assignment if tier changed or new subscriber
                if sub['current_tier'] != assignment['tier_id']:
                    if save_pool_assignment_to_db(
                        sub['msisdn'], 
                        assignment, 
                        previous_tier_id=sub['current_tier']
                    ):
                        summary['tier_moves'] += 1
                
                # Update summary
                summary['successful_assignments'] += 1
                summary['total_cost'] += assignment['tier_cost']
                
                tier_name = assignment['tier_name']
                summary['tier_distribution'][tier_name] = \
                    summary['tier_distribution'].get(tier_name, 0) + 1
                
            except Exception as e:
                logger.error(f"Error optimizing {sub['msisdn']}: {e}")
                continue
        
        # Calculate savings
        summary['estimated_savings'] = baseline_cost - summary['total_cost']
        summary['savings_percentage'] = round(
            (summary['estimated_savings'] / baseline_cost) * 100, 2
        )
        
        # Save optimization log
        save_optimization_log(summary)
        
        logger.info(f"Optimization complete: {summary['successful_assignments']} subscribers, "
                   f"${summary['total_cost']:.2f} total cost, "
                   f"${summary['estimated_savings']:.2f} savings ({summary['savings_percentage']}%)")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in batch optimization: {e}")
        return None


def save_optimization_log(summary):
    """
    Save optimization results to log table
    
    Args:
        summary (dict): Optimization summary
    
    Returns:
        bool: True if successful
    """
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    query = text("""
        INSERT INTO pool_optimization_log (
            calculation_date, billing_month, total_subscribers,
            tier_distribution, total_cost, 
            potential_cost_without_optimization, cost_savings,
            moved_subscribers
        ) VALUES (
            :calculation_date, :billing_month, :total_subscribers,
            :tier_distribution, :total_cost,
            :potential_cost, :cost_savings,
            :moved_subscribers
        )
    """)
    
    try:
        import json
        with engine.begin() as conn:
            conn.execute(query, {
                'calculation_date': datetime.now().date(),
                'billing_month': billing_start.strftime('%Y-%m-%d'),
                'total_subscribers': summary['total_subscribers'],
                'tier_distribution': json.dumps(summary['tier_distribution']),
                'total_cost': summary['total_cost'],
                'potential_cost': summary['total_cost'] + summary['estimated_savings'],
                'cost_savings': summary['estimated_savings'],
                'moved_subscribers': summary['tier_moves']
            })
        logger.info("Saved optimization log to database")
        return True
    except Exception as e:
        logger.error(f"Error saving optimization log: {e}")
        return False


# Test function
if __name__ == "__main__":
    print("Testing Pool Optimization Engine\n")
    print("=" * 50)
    
    # Test 1: Single subscriber optimization
    test_msisdn = "2026853028"
    
    print(f"\n1. Optimizing assignment for {test_msisdn}...")
    result = optimize_subscriber_assignment(test_msisdn, force_retrain=True)
    
    if result:
        print("\n✅ Optimization Result:")
        print(f"   Predicted Usage: {result['prediction']['predicted_total_gb']} GB")
        print(f"   Confidence Upper: {result['prediction']['confidence_upper_gb']} GB")
        print(f"\n   Assigned Tier: {result['assignment']['tier_name']}")
        print(f"   Tier Cost: ${result['assignment']['tier_cost']}")
        print(f"   Tier Cap: {result['assignment']['tier_cap_gb']} GB")
        print(f"   Headroom: {result['assignment']['headroom_gb']} GB")
        print(f"   Overage Risk: {result['assignment']['overage_risk']}")
        
        print("\n   Cost Breakdown (All Tiers):")
        for tier in result['cost_breakdown']:
            exceed_flag = "⚠️ OVERAGE" if tier['will_exceed'] else "✅ Safe"
            print(f"      {tier['tier_name']}: ${tier['total_cost']:.2f} {exceed_flag}")
        
        # Save assignment
        if save_pool_assignment_to_db(test_msisdn, result['assignment']):
            print("\n✅ Assignment saved to database")
    else:
        print("\n❌ Optimization failed")
    
    # Test 2: Show tier pricing table
    print("\n2. Tier Pricing Structure:")
    for tier_code, tier in TIER_PRICING.items():
        print(f"   {tier_code}: {tier['tier_name']} - "
              f"{tier['cap_gb']}GB @ ${tier['cost']} "
              f"(Overage: ${tier['overage_per_gb']}/GB)")
    
    print("\n" + "=" * 50)