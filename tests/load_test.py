"""
Load Test - MVNO Intelligence Hub
Validates system performance at 30K-50K subscriber scale.
Measures ingestion, prediction, and optimization throughput.
"""

import random
import time
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from config.database import engine
from config.logging_config import setup_logging

logger = setup_logging(__name__)

# CONFIGURATION
TARGET_SUBSCRIBERS = 30000
DAYS_OF_HISTORY = 90
BATCH_SIZE = 1000  # Insert in batches to avoid memory issues


def generate_msisdn():
    """Generate a realistic 10-digit US phone number"""
    area_codes = ['404', '678', '770', '470', '214', '972', '469', '312', '773', '832']
    return f"{random.choice(area_codes)}{random.randint(1000000, 9999999)}"


def seed_subscribers(num_subscribers=TARGET_SUBSCRIBERS):
    """Insert synthetic subscribers into the subscribers table"""
    logger.info(f"🌱 Seeding {num_subscribers:,} synthetic subscribers...")
    start = time.time()

    msisdns = [generate_msisdn() for _ in range(num_subscribers)]

    query = text("""
        INSERT INTO subscribers (msisdn, tenant_id, current_status, created_at, updated_at)
        VALUES (:msisdn, 1, 'ACTIVE', NOW(), NOW())
        ON CONFLICT DO NOTHING
    """)

    with engine.begin() as conn:
        for i in range(0, len(msisdns), BATCH_SIZE):
            batch = msisdns[i:i+BATCH_SIZE]
            conn.execute(query, [{'msisdn': m} for m in batch])
            if (i // BATCH_SIZE) % 10 == 0:
                logger.info(f"  Inserted {min(i+BATCH_SIZE, num_subscribers):,} / {num_subscribers:,} subscribers...")

    elapsed = time.time() - start
    logger.info(f"✅ Subscriber seeding complete in {elapsed:.2f}s")
    return msisdns


def seed_usage_data(msisdns, days=DAYS_OF_HISTORY):
    """Insert synthetic daily_usage records for all subscribers"""
    logger.info(f"📊 Seeding {days} days of usage for {len(msisdns):,} subscribers...")
    start = time.time()

    query = text("""
        INSERT INTO daily_usage (msisdn, usage_time, bytes_up, bytes_down)
        VALUES (:msisdn, :usage_time, :bytes_up, :bytes_down)
        ON CONFLICT DO NOTHING
    """)

    end_date = datetime.now().date()
    batch = []

    for msisdn in msisdns:
        # Not every subscriber uses data every day
        active_days = random.randint(days // 3, days)
        usage_dates = sorted(random.sample(
            [(end_date - timedelta(days=d)) for d in range(days)],
            min(active_days, days)
        ))

        for day in usage_dates:
            # 1-5 sessions per day
            for _ in range(random.randint(1, 5)):
                hour = random.randint(6, 23)
                batch.append({
                    'msisdn': msisdn,
                    'usage_time': datetime.combine(day, datetime.min.time()).replace(hour=hour),
                    'bytes_up': random.randint(100000, 50000000),
                    'bytes_down': random.randint(500000, 200000000)
                })

        if len(batch) >= BATCH_SIZE * 10:
            with engine.begin() as conn:
                conn.execute(query, batch)
            batch = []

    if batch:
        with engine.begin() as conn:
            conn.execute(query, batch)

    elapsed = time.time() - start
    logger.info(f"✅ Usage data seeding complete in {elapsed:.2f}s")


def seed_pool_assignments(msisdns):
    """Assign subscribers to pool tiers"""
    logger.info(f"🏊 Assigning {len(msisdns):,} subscribers to pool tiers...")
    start = time.time()

    # Tier distribution: most on basic, some on higher tiers
    tier_weights = {1: 0.60, 100: 0.25, 101: 0.15}
    tiers = list(tier_weights.keys())
    weights = list(tier_weights.values())

    query = text("""
        INSERT INTO pool_assignments (msisdn, tier_id, billing_month, assigned_date)
        VALUES (:msisdn, :tier_id, :billing_month, NOW())
        ON CONFLICT DO NOTHING
    """)

    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    billing_month = billing_start.strftime('%Y-%m')

    with engine.begin() as conn:
        for i in range(0, len(msisdns), BATCH_SIZE):
            batch = msisdns[i:i+BATCH_SIZE]
            conn.execute(query, [
                {
                    'msisdn': m,
                    'tier_id': random.choices(tiers, weights=weights)[0],
                    'billing_month': billing_month
                }
                for m in batch
            ])

    elapsed = time.time() - start
    logger.info(f"✅ Pool assignments complete in {elapsed:.2f}s")


def run_aggregation_benchmark(msisdns, sample_size=1000):
    """Benchmark the aggregation pipeline on a sample"""
    logger.info(f"⚡ Benchmarking aggregation on {sample_size:,} subscribers...")
    start = time.time()

    from src.features.usage_aggregation import populate_daily_aggregates
    populate_daily_aggregates()

    elapsed = time.time() - start
    rate = sample_size / elapsed
    logger.info(f"✅ Aggregation: {elapsed:.2f}s for {sample_size:,} subscribers ({rate:.0f}/sec)")
    return elapsed


def run_prediction_benchmark(msisdns, sample_size=100):
    """Benchmark prediction on a sample of subscribers"""
    logger.info(f"🔮 Benchmarking predictions on {sample_size} subscribers...")
    start = time.time()
    sample = random.sample(msisdns, min(sample_size, len(msisdns)))
    success = 0

    from src.models.current_month_predictor import predict_for_subscriber, save_prediction_to_db
    for msisdn in sample:
        result = predict_for_subscriber(msisdn, retrain=True)
        if result:
            save_prediction_to_db(result)
            success += 1

    elapsed = time.time() - start
    rate = success / elapsed if elapsed > 0 else 0
    projected_30k = (TARGET_SUBSCRIBERS / rate / 60) if rate > 0 else 0
    logger.info(f"✅ Predictions: {success}/{sample_size} succeeded in {elapsed:.2f}s ({rate:.1f}/sec)")
    logger.info(f"📈 Projected time for {TARGET_SUBSCRIBERS:,} subscribers: {projected_30k:.1f} minutes")
    return elapsed, rate


def check_db_performance():
    """Check table sizes and query performance"""
    logger.info("🔍 Checking database performance...")

    queries = {
        "Subscriber count": "SELECT COUNT(*) FROM subscribers",
        "Usage records": "SELECT COUNT(*) FROM daily_usage",
        "Daily aggregates": "SELECT COUNT(*) FROM usage_daily_agg",
        "Pool assignments": "SELECT COUNT(*) FROM pool_assignments",
    }

    with engine.connect() as conn:
        for label, q in queries.items():
            start = time.time()
            result = conn.execute(text(q)).scalar()
            elapsed = (time.time() - start) * 1000
            logger.info(f"  {label}: {result:,} rows ({elapsed:.1f}ms)")


def cleanup_load_test_data(msisdns):
    """Remove synthetic test data, keeping real subscriber data"""
    logger.info("🧹 Cleaning up load test data...")
    real_msisdns = ['4042778501', '4043846345', '9043869499', '4043896924',
                    '4046427108', '4043896659', '2272773440', '4045933326',
                    '2404381287', '4043896924']

    test_msisdns = [m for m in msisdns if m not in real_msisdns]

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM daily_usage WHERE msisdn = ANY(:msisdns)"),
                     {'msisdns': test_msisdns})
        conn.execute(text("DELETE FROM usage_daily_agg WHERE msisdn = ANY(:msisdns)"),
                     {'msisdns': test_msisdns})
        conn.execute(text("DELETE FROM pool_assignments WHERE msisdn = ANY(:msisdns)"),
                     {'msisdns': test_msisdns})
        conn.execute(text("DELETE FROM subscribers WHERE msisdn = ANY(:msisdns)"),
                     {'msisdns': test_msisdns})

    logger.info(f"✅ Cleaned up {len(test_msisdns):,} synthetic subscribers")


def run_load_test(cleanup=True):
    """Full load test suite"""
    print("\n" + "="*60)
    print(f"  MVNO INTELLIGENCE HUB - LOAD TEST")
    print(f"  Target Scale: {TARGET_SUBSCRIBERS:,} subscribers")
    print(f"  History Depth: {DAYS_OF_HISTORY} days")
    print("="*60 + "\n")

    total_start = time.time()

    # Phase 1: Seed data
    msisdns = seed_subscribers(TARGET_SUBSCRIBERS)
    seed_usage_data(msisdns, DAYS_OF_HISTORY)
    seed_pool_assignments(msisdns)

    # Phase 2: Benchmarks
    check_db_performance()
    agg_time = run_aggregation_benchmark(msisdns)
    pred_time, pred_rate = run_prediction_benchmark(msisdns, sample_size=100)

    # Phase 3: Results
    total_elapsed = time.time() - total_start
    print("\n" + "="*60)
    print("  LOAD TEST RESULTS")
    print("="*60)
    print(f"  Total test duration:        {total_elapsed:.1f}s")
    print(f"  Aggregation throughput:     {TARGET_SUBSCRIBERS / agg_time:.0f} subscribers/sec")
    print(f"  Prediction throughput:      {pred_rate:.1f} subscribers/sec")
    print(f"  Projected 30K batch time:   {TARGET_SUBSCRIBERS / pred_rate / 60:.1f} minutes")
    print("="*60 + "\n")

    # Phase 4: Cleanup
    if cleanup:
        cleanup_load_test_data(msisdns)

    return {
        'total_time': total_elapsed,
        'agg_throughput': TARGET_SUBSCRIBERS / agg_time,
        'pred_throughput': pred_rate
    }


if __name__ == "__main__":
    run_load_test(cleanup=True)
