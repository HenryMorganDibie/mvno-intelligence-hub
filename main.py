"""
MVNO Intelligence Hub - Main Orchestrator
Coordinates the full lifecycle: Individual Analysis -> Community Matching -> Reporting
"""

from config.logging_config import setup_logging
from src.features.usage_aggregation import populate_daily_aggregates
from src.models.current_month_predictor import predict_for_subscriber
from src.optimization.pool_optimizer import optimize_subscriber_assignment
from src.optimization.donation_calculator import calculate_donation_for_subscriber, save_donation_threshold_to_db
from src.optimization.donation_matcher import execute_matching_cycle
from src.reports.impact_summary import print_impact_report  # <--- NEW IMPORT

# Initialize professional logging
logger = setup_logging(__name__)

def run_subscriber_pipeline(msisdn):
    """Runs the individual intelligence loop for a single subscriber"""
    logger.info(f"--- Starting Pipeline for {msisdn} ---")
    
    try:
        # STEP 1: Generate Prediction
        logger.info(f"Step 1 ({msisdn}): Generating usage prediction...")
        prediction = predict_for_subscriber(msisdn, retrain=True)
        if not prediction:
            raise Exception("Prediction phase failed.")

        # STEP 2: Optimize Pool Tier
        logger.info(f"Step 2 ({msisdn}): Checking for optimal tier assignment...")
        optimize_subscriber_assignment(msisdn)
        
        # STEP 3: Calculate Donation Potential
        logger.info(f"Step 3 ({msisdn}): Updating donation thresholds...")
        donation = calculate_donation_for_subscriber(msisdn)
        if donation:
            save_donation_threshold_to_db(donation)
            
        logger.info(f"--- Pipeline Finished for {msisdn} ---")
        return True

    except Exception as e:
        logger.error(f"Pipeline crashed for {msisdn}: {e}")
        return False

def run_batch_process():
    """
    The Full Fleet Operation:
    1. Global Sync
    2. Individual Analysis
    3. Community Matching
    4. Impact Reporting
    """
    subscribers = ["2026853028", "2026999999"]
    
    logger.info(f"🚀 Starting Global Batch Processing for {len(subscribers)} subscribers...")

    # GLOBAL STEP 0: Sync Usage Data
    logger.info("Step 0: Syncing global usage aggregates...")
    populate_daily_aggregates() 
    
    # INDIVIDUAL STEPS 1-3: Analysis
    for msisdn in subscribers:
        run_subscriber_pipeline(msisdn)
        
    # GLOBAL STEP 4: Matching
    logger.info("🏁 Step 4: Executing Community Donation Matching...")
    execute_matching_cycle()
    
    # GLOBAL STEP 5: Reporting
    logger.info("📊 Step 5: Generating Community Impact Report...")
    print_impact_report()
    
    logger.info("✅ Global Batch Processing Complete.")

if __name__ == "__main__":
    run_batch_process()