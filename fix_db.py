from sqlalchemy import text
from config.database import engine

# simplified to only drop the table to avoid Postgres "WrongObjectType" errors
setup_sql = """
DROP TABLE IF EXISTS data_donations CASCADE;

CREATE TABLE data_donations (
    id SERIAL PRIMARY KEY,
    donor_msisdn VARCHAR(20),
    recipient_msisdn VARCHAR(20) NOT NULL,
    amount_gb DECIMAL(10, 2) NOT NULL,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'COMPLETED'
);

CREATE INDEX idx_donor_msisdn ON data_donations(donor_msisdn);
CREATE INDEX idx_recipient_msisdn ON data_donations(recipient_msisdn);
"""

try:
    with engine.connect() as conn:
        conn.execute(text(setup_sql))
        conn.commit()
        print("✅ Clean Slate: 'data_donations' table recreated (empty).")
except Exception as e:
    print(f"❌ Error: {e}")
