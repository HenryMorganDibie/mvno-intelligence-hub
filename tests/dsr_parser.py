import csv
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# 1. Load Environment Variables
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. Setup Database Engine
try:
    connection_url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )
    engine = create_engine(connection_url)
    logger.info("✅ Database engine initialized.")
except Exception as e:
    logger.error(f"❌ Failed to initialize database engine: {e}")
    raise

def clean_val(val):
    """Handles NULLs and '0000-00-00' formats."""
    if not val:
        return None
    val = val.strip().strip('"')
    if val in ["", "0000-00-00 00:00:00", "0000-00-00", "NULL"]:
        return None
    return val

def parse_dsr_file(file_path):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    logger.info(f"🚀 Starting ingestion for: {file_path}")
    records = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or not line.endswith(';'):
                    continue
                
                # Strip the trailing semicolon
                line = line[:-1]
                
                reader = csv.reader([line])
                row = next(reader)

                if len(row) < 18:
                    continue

                # Mapped specifically to your SQL Schema:
                # SQL 'data_bytes' <-> CSV Column 9
                # SQL 'flag'       <-> CSV Column 10
                record = {
                    "usage_date": clean_val(row[0]),
                    "msisdn": clean_val(row[1]),
                    "imsi": clean_val(row[2]),
                    "tenant_id": int(row[3]) if row[3].isdigit() else 0,
                    "billing_code": clean_val(row[4]),
                    "active_status": int(row[5]) if row[5].isdigit() else 0,
                    "suspend_status": int(row[6]) if row[6].isdigit() else 0,
                    "voice_minutes": float(row[7]) if row[7] else 0.0,
                    "sms_units": int(float(row[8])) if row[8] else 0,
                    "data_bytes": float(row[9]) if row[9] else 0.0, 
                    "flag": clean_val(row[10]),
                    "subscriber_state": clean_val(row[11]),
                    "activation_date": clean_val(row[12]),
                    "suspend_date": clean_val(row[13]),
                    "deactivation_date": clean_val(row[14]),
                    "bundle_id": clean_val(row[15]),
                    "expiration_date": clean_val(row[16]),
                    "iccid": clean_val(row[17]),
                    "zipcode": clean_val(row[18]) if len(row) > 18 else None
                }
                records.append(record)

        if records:
            # The keys here must match the keys in the 'record' dictionary above
            insert_sql = text("""
                INSERT INTO daily_subscriber_reports (
                    usage_date, msisdn, imsi, tenant_id, billing_code, 
                    active_status, suspend_status, voice_minutes, sms_units, 
                    data_bytes, flag, subscriber_state, activation_date, 
                    suspend_date, deactivation_date, bundle_id, expiration_date, 
                    iccid, zipcode
                ) VALUES (
                    :usage_date, :msisdn, :imsi, :tenant_id, :billing_code, 
                    :active_status, :suspend_status, :voice_minutes, :sms_units, 
                    :data_bytes, :flag, :subscriber_state, :activation_date, 
                    :suspend_date, :deactivation_date, :bundle_id, :expiration_date, 
                    :iccid, :zipcode
                )
            """)
            
            with engine.begin() as conn:
                conn.execute(insert_sql, records)
            logger.info(f"✅ Successfully ingested {len(records)} records.")

    except Exception as e:
        logger.error(f"❌ Ingestion Error: {e}")

if __name__ == "__main__":
    SAMPLE_FILE = "data/samples/DSR_Sample_20260201.csv"
    parse_dsr_file(SAMPLE_FILE)