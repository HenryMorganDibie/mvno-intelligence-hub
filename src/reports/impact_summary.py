from sqlalchemy import text
from config.database import engine

def print_impact_report():
    query = text("""
        SELECT 
            COUNT(DISTINCT recipient_msisdn) as users_saved,
            SUM(amount_gb) as total_gb_gifted,
            SUM(amount_gb) * 10 as estimated_savings_usd
        FROM data_donations
    """)
    
    with engine.connect() as conn:
        res = conn.execute(query).fetchone()
        print("\n--- 🌍 COMMUNITY IMPACT REPORT ---")
        print(f"Subscribers Saved from Overages: {res[0]}")
        print(f"Total Data Redistributed:       {res[1]:.2f} GB")
        print(f"Estimated Customer Savings:     ${res[2]:.2f}")
        print("---------------------------------\n")

if __name__ == "__main__":
    print_impact_report()