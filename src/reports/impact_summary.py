from sqlalchemy import text
from config.database import engine
from src.features.usage_aggregation import get_current_billing_cycle_dates

def print_impact_report():
    billing_start, billing_end = get_current_billing_cycle_dates()

    query = text("""
        SELECT
            COUNT(DISTINCT recipient_msisdn) as users_saved,
            COALESCE(SUM(amount_gb), 0) as total_gb_gifted,
            COALESCE(SUM(amount_gb), 0) * 10 as estimated_savings_usd
        FROM data_donations
        WHERE transaction_date::date >= :billing_start
        AND transaction_date::date <= :billing_end
    """)

    with engine.connect() as conn:
        res = conn.execute(query, {
            'billing_start': billing_start,
            'billing_end': billing_end
        }).fetchone()
        print("\n--- 🌍 COMMUNITY IMPACT REPORT ---")
        print(f"Subscribers Saved from Overages: {res[0]}")
        print(f"Total Data Redistributed:       {res[1]:.2f} GB")
        print(f"Estimated Customer Savings:     ${res[2]:.2f}")
        print("---------------------------------\n")

if __name__ == "__main__":
    print_impact_report()
