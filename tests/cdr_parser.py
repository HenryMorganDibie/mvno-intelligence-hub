import csv
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# 1. Setup Environment and Database
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_engine():
    connection_url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
    )
    return create_engine(connection_url)

engine = get_engine()

def clean(val):
    if not val: return None
    val = val.strip().strip('"')
    return None if val in ["", "NULL", "0000-00-00 00:00:00"] else val

def parse_cdr_file(file_path):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    # Batches for bulk insertion
    voice_records = []
    sms_records = []
    data_records = []

    logger.info(f"📂 Processing CDR file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or not line.endswith(';'): continue
                line = line[:-1] # Remove semicolon

                reader = csv.reader([line])
                row = next(reader)
                
                # Column 4 (index 4) is USAGE_TYPE per specs
                usage_type = row[4].upper()

                # --- VOICE LOGIC ---
                if "VOICE" in usage_type:
                    voice_records.append({
                        "effective_date": clean(row[6]),
                        "tenant_id": int(row[1]) if row[1].isdigit() else 0,
                        "msisdn": clean(row[2]),
                        "usage_type": clean(row[4]),
                        "other_party_number": clean(row[7]),
                        "duration_minutes": int(row[21]) if row[21].isdigit() else 0,
                        "duration_seconds": int(row[22]) if row[22].isdigit() else 0,
                        "billing_code": clean(row[34]) if len(row) > 34 else None
                    })

                # --- SMS LOGIC ---
                elif "SMS" in usage_type:
                    sms_records.append({
                        "effective_date": clean(row[6]),
                        "tenant_id": int(row[1]) if row[1].isdigit() else 0,
                        "msisdn": clean(row[2]),
                        "usage_type": clean(row[4]),
                        "message_count": int(row[21]) if row[21].isdigit() else 1,
                        "billing_code": clean(row[33]) if len(row) > 33 else None
                    })

                # --- DATA (GPRS) LOGIC ---
                elif "GPRS" in usage_type or "DATA" in usage_type:
                    data_records.append({
                        "effective_date": clean(row[6]),
                        "tenant_id": int(row[1]) if row[1].isdigit() else 0,
                        "msisdn": clean(row[2]),
                        "usage_type": clean(row[4]),
                        "access_point_name": clean(row[12]),
                        "total_volume_bytes": float(row[20]) if row[20] else 0.0,
                        "duration_seconds": int(row[21]) if row[21].isdigit() else 0,
                        "billing_code": clean(row[40]) if len(row) > 40 else None
                    })

        # --- BULK INSERTIONS ---
        with engine.begin() as conn:
            if voice_records:
                conn.execute(text("""
                    INSERT INTO cdr_voice (effective_date, tenant_id, msisdn, usage_type, other_party_number, duration_minutes, duration_seconds, billing_code)
                    VALUES (:effective_date, :tenant_id, :msisdn, :usage_type, :other_party_number, :duration_minutes, :duration_seconds, :billing_code)
                """), voice_records)
                logger.info(f"🎤 Inserted {len(voice_records)} Voice records")

            if sms_records:
                conn.execute(text("""
                    INSERT INTO cdr_sms (effective_date, tenant_id, msisdn, usage_type, message_count, billing_code)
                    VALUES (:effective_date, :tenant_id, :msisdn, :usage_type, :message_count, :billing_code)
                """), sms_records)
                logger.info(f"💬 Inserted {len(sms_records)} SMS records")

            if data_records:
                conn.execute(text("""
                    INSERT INTO cdr_data (effective_date, tenant_id, msisdn, usage_type, access_point_name, total_volume_bytes, duration_seconds, billing_code)
                    VALUES (:effective_date, :tenant_id, :msisdn, :usage_type, :access_point_name, :total_volume_bytes, :duration_seconds, :billing_code)
                """), data_records)
                logger.info(f"📶 Inserted {len(data_records)} Data records")

    except Exception as e:
        logger.error(f"❌ CDR Ingestion Error: {e}")

if __name__ == "__main__":
    parse_cdr_file("data/samples/CDR_PartnerID_20260201.csv")