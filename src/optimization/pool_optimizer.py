"""
Pool Optimization Engine
Assigns subscribers to optimal data pool tiers to minimize costs.
Production-ready: Uses centralized logging, database, and logic safety checks.
"""

import os
import json
from datetime import datetime
from sqlalchemy import text

# Professional Imports
from config.logging_config import setup_logging
from config.database import engine

# Initialize professional logger
logger = setup_logging(__name__)

# Tier pricing structure (The Source of Truth for Costs)
TIER_PRICING = {
    'PPP1': {'tier_id': 1, 'tier_name': '1GB Pool',  'cap_gb': 1.0,  'cost': 3.95,  'overage_per_gb': 4.50},
    'PPP2': {'tier_id': 2, 'tier_name': '5GB Pool',  'cap_gb': 5.0,  'cost': 12.00, 'overage_per_gb': 4.00},
    'PPP3': {'tier_id': 3, 'tier_name': '10GB Pool', 'cap_gb': 10.0, 'cost': 19.00, 'overage_per_gb': 3.50},
    'PPP4': {'tier_id': 4, 'tier_name': '15GB Pool', 'cap_gb': 15.0, 'cost': 24.50, 'overage_per_gb': 2.50},
    'PPP5': {'tier_id': 5, 'tier_name': '30GB Pool', 'cap_gb': 30.0, 'cost': 45.00, 'overage_per_gb': 2.00},
    'PPP6': {'tier_id': 6, 'tier_name': '40GB Pool', 'cap_gb': 40.0, 'cost': 58.00, 'overage_per_gb': 1.80}
}

def assign_optimal_tier(predicted_usage_gb, confidence_upper_gb, safety_buffer=0.10):
    """Cheapest tier logic with safety margin"""
    required_capacity_gb = confidence_upper_gb * (1 + safety_buffer)
    
    # Sort tiers by cost ascending
    sorted_tiers = sorted(TIER_PRICING.items(), key=lambda x: x[1]['cost'])
    
    for tier_code, tier_info in sorted_tiers:
        if tier_info['cap_gb'] >= required_capacity_gb:
            return {
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
    
    # Fallback to Max Tier
    largest_tier = TIER_PRICING['PPP6']
    return {
        'tier_code': 'PPP6', 'tier_id': largest_tier['tier_id'], 'tier_name': largest_tier['tier_name'],
        'tier_cost': largest_tier['cost'], 'tier_cap_gb': largest_tier['cap_gb'],
        'predicted_usage_gb': round(predicted_usage_gb, 2),
        'confidence_upper_gb': round(confidence_upper_gb, 2),
        'required_capacity_gb': round(required_capacity_gb, 2),
        'headroom_gb': round(largest_tier['cap_gb'] - required_capacity_gb, 2),
        'overage_risk': 'HIGH', 'reason': 'exceeds_max_tier'
    }

def calculate_cost_comparison(predicted_usage_gb, confidence_upper_gb):
    """Generates cost scenarios for auditing and UI display"""
    results = []
    for tier_code, tier_info in TIER_PRICING.items():
        base_cost = tier_info['cost']
        overage_gb = max(0, confidence_upper_gb - tier_info['cap_gb'])
        overage_cost = overage_gb * tier_info['overage_per_gb']
        
        results.append({
            'tier_code': tier_code,
            'tier_name': tier_info['tier_name'],
            'total_cost': round(base_cost + overage_cost, 2),
            'will_exceed': overage_gb > 0
        })
    return sorted(results, key=lambda x: x['total_cost'])

def optimize_subscriber_assignment(msisdn, force_retrain=False):
    """Single MSISDN workflow: Predict -> Assign -> Compare"""
    from src.models.current_month_predictor import predict_for_subscriber
    
    prediction = predict_for_subscriber(msisdn, retrain=force_retrain)
    if not prediction:
        return None
    
    assignment = assign_optimal_tier(
        prediction['predicted_total_gb'],
        prediction['confidence_upper_gb']
    )
    
    cost_breakdown = calculate_cost_comparison(
        prediction['predicted_total_gb'],
        prediction['confidence_upper_gb']
    )
    
    return {
        'msisdn': msisdn,
        'prediction': prediction,
        'assignment': assignment,
        'cost_breakdown': cost_breakdown,
        'optimized_at': datetime.now().isoformat()
    }

def save_pool_assignment_to_db(msisdn, assignment, previous_tier_id=None):
    """Persists the recommendation to the database"""
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
        logger.info(f"Optimized Tier Saved: {msisdn} -> {assignment['tier_name']}")
        return True
    except Exception as e:
        logger.error(f"DB Error saving assignment for {msisdn}: {e}")
        return False

def batch_optimize_all_subscribers():
    """Heavy lifter: Optimizes the whole fleet and logs financial impact"""
    query = text("""
        SELECT s.msisdn, pa.tier_id as current_tier_id
        FROM subscribers s
        LEFT JOIN LATERAL (
            SELECT tier_id FROM pool_assignments 
            WHERE msisdn = s.msisdn ORDER BY assigned_date DESC LIMIT 1
        ) pa ON TRUE
        WHERE s.current_status = 'ACTIVE'
    """)
    
    try:
        with engine.connect() as conn:
            subscribers = [{'msisdn': row[0], 'current_tier': row[1]} for row in conn.execute(query)]
        
        logger.info(f"Starting batch optimization for {len(subscribers)} subscribers...")
        summary = {
            'total_subscribers': len(subscribers), 'successful_assignments': 0,
            'tier_moves': 0, 'tier_distribution': {}, 'total_cost': 0, 'estimated_savings': 0
        }
        
        # We assume baseline is max tier for unoptimized accounts
        baseline_cost = len(subscribers) * TIER_PRICING['PPP6']['cost']
        
        for sub in subscribers:
            opt = optimize_subscriber_assignment(sub['msisdn'])
            if not opt: continue
            
            assignment = opt['assignment']
            if sub['current_tier'] != assignment['tier_id']:
                if save_pool_assignment_to_db(sub['msisdn'], assignment, sub['current_tier']):
                    summary['tier_moves'] += 1
            
            summary['successful_assignments'] += 1
            summary['total_cost'] += assignment['tier_cost']
            t_name = assignment['tier_name']
            summary['tier_distribution'][t_name] = summary['tier_distribution'].get(t_name, 0) + 1
        
        summary['estimated_savings'] = baseline_cost - summary['total_cost']
        save_optimization_log(summary)
        return summary
    except Exception as e:
        logger.error(f"Batch optimization failed: {e}")
        return None

def save_optimization_log(summary):
    """Saves the high-level summary for the dashboard"""
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    query = text("""
        INSERT INTO pool_optimization_log (
            calculation_date, billing_month, total_subscribers,
            tier_distribution, total_cost, 
            potential_cost_without_optimization, cost_savings,
            moved_subscribers
        ) VALUES (
            NOW(), :billing_month, :total_subscribers,
            :tier_distribution, :total_cost, :potential_cost, :cost_savings, :moved_subscribers
        )
    """)
    
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                'billing_month': billing_start.strftime('%Y-%m-%d'),
                'total_subscribers': summary['total_subscribers'],
                'tier_distribution': json.dumps(summary['tier_distribution']),
                'total_cost': summary['total_cost'],
                'potential_cost': summary['total_cost'] + summary['estimated_savings'],
                'cost_savings': summary['estimated_savings'],
                'moved_subscribers': summary['tier_moves']
            })
        logger.info("Batch optimization log entry created.")
    except Exception as e:
        logger.error(f"Failed to save optimization log: {e}")

if __name__ == "__main__":
    test_msisdn = "2026853028"
    logger.info("Testing Pool Optimization Engine")
    result = optimize_subscriber_assignment(test_msisdn)
    
    if result:
        print("\n" + "="*50)
        print(f"OPTIMIZATION FOR: {test_msisdn}")
        print(f"Predicted: {result['prediction']['predicted_total_gb']} GB")
        print(f"Decision:  {result['assignment']['tier_name']} (${result['assignment']['tier_cost']})")
        print(f"Risk:      {result['assignment']['overage_risk']}")
        print("="*50 + "\n")
        save_pool_assignment_to_db(test_msisdn, result['assignment'])