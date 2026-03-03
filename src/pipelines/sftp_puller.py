import os
import glob
import logging
import paramiko
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# SFTP Config
SFTP_HOST = "cdr.mvnoc.ai"
SFTP_PORT = 10022
SFTP_USER = "culturewireless"
SFTP_PASS = "oogh9caeghaePooT"

# Remote paths
CDR_REMOTE = "cdr"
DSR_REMOTE = "subscriber_report"

# Local paths
CDR_LOCAL = os.path.expanduser("~/mvno-intelligence-hub/data/raw/usage_reports/")
DSR_LOCAL = os.path.expanduser("~/mvno-intelligence-hub/data/raw/subscriber_reports/")

# DB
DB_URL = "postgresql://postgres@localhost:5432/mvno_usage_db"

# Only pull files from today
TODAY = datetime.now().strftime("%Y%m%d")

os.makedirs(CDR_LOCAL, exist_ok=True)
os.makedirs(DSR_LOCAL, exist_ok=True)


def connect_sftp():
    log.info(f"Connecting to {SFTP_HOST}:{SFTP_PORT}...")
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USER, password=SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    log.info("Connected.")
    return sftp, transport


def pull_cdr_files(sftp):
    log.info(f"Listing CDR files for today ({TODAY})...")
    all_files = sftp.listdir(CDR_REMOTE)
    todays_files = [f for f in all_files if "_DATA_" in f and TODAY in f]
    already_local = set(os.listdir(CDR_LOCAL))
    new_files = [f for f in todays_files if f not in already_local]

    if not new_files:
        log.info("No new CDR files to download.")
        return []

    log.info(f"Downloading {len(new_files)} new CDR files...")
    downloaded = []
    for fname in sorted(new_files):
        local_path = os.path.join(CDR_LOCAL, fname)
        try:
            sftp.get(f"{CDR_REMOTE}/{fname}", local_path)
            log.info(f"  ✅ {fname}")
            downloaded.append(local_path)
        except Exception as e:
            log.error(f"  ❌ {fname}: {e}")

    log.info(f"CDR download complete: {len(downloaded)} files.")
    return downloaded


def pull_dsr_files(sftp):
    fname = f"DSR_97_{TODAY}.csv"
    local_path = os.path.join(DSR_LOCAL, fname)

    if os.path.exists(local_path):
        log.info(f"DSR already downloaded: {fname}")
        return []

    log.info(f"Downloading DSR: {fname}...")
    try:
        sftp.get(f"{DSR_REMOTE}/{fname}", local_path)
        log.info(f"  ✅ {fname}")
        return [local_path]
    except Exception as e:
        log.error(f"  ❌ {fname}: {e}")
        return []


def ingest_cdr_files(file_paths):
    """Ingest only the specific new CDR files."""
    if not file_paths:
        return
    engine = create_engine(DB_URL)
    all_data = []
    success, errors = 0, 0
    for file_path in file_paths:
        if os.path.getsize(file_path) == 0:
            continue
        try:
            df = pd.read_csv(file_path, header=None, quotechar='"', on_bad_lines='skip')
            subset = df[[2, 6, 27, 28]].copy()
            subset.columns = ['msisdn', 'usage_time', 'bytes_up', 'bytes_down']
            subset['bytes_up'] = pd.to_numeric(subset['bytes_up'], errors='coerce').fillna(0)
            subset['bytes_down'] = pd.to_numeric(subset['bytes_down'], errors='coerce').fillna(0)
            all_data.append(subset)
            success += 1
        except Exception as e:
            errors += 1
            log.error(f"CDR parse error {os.path.basename(file_path)}: {e}")

    if all_data:
        pd.concat(all_data).to_sql('daily_usage', engine, if_exists='append', index=False)
    log.info(f"CDR ingestion: {success} ok, {errors} errors.")


def ingest_dsr_files(file_paths):
    """Ingest only the specific new DSR files."""
    if not file_paths:
        return
    engine = create_engine(DB_URL)
    mapping = {
        'USAGE_DATE': 'usage_date', 'MSISDN': 'msisdn', 'IMSI': 'imsi',
        'TENANT_ID': 'tenant_id', 'BILLING_CODE': 'billing_code',
        'ACTIVE_STATUS': 'active_status', 'SUSPEND_STATUS': 'suspend_status',
        'VOICE': 'voice_minutes', 'SMS': 'sms_units', 'GPRS': 'data_bytes',
        'FLAG': 'flag', 'SUBSCRIBER_STATE': 'subscriber_state',
        'ACTIVATION_DATE': 'activation_date', 'SUSPEND_DATE': 'suspend_date',
        'DEACTIVATION_DATE': 'deactivation_date', 'BUNDLE_ID': 'bundle_id',
        'EXPIRATION_DATE': 'expiration_date', 'ICCID': 'iccid', 'ZIPCODE': 'zipcode'
    }
    for file_path in file_paths:
        try:
            df = pd.read_csv(file_path)
            df = df.rename(columns=mapping)
            df['usage_date'] = pd.to_datetime(df['usage_date'])
            df.to_sql('daily_subscriber_reports', engine, if_exists='append', index=False)
            log.info(f"DSR ingested: {os.path.basename(file_path)}")
        except Exception as e:
            if "duplicate key" in str(e):
                log.info(f"DSR already exists: {os.path.basename(file_path)}")
            else:
                log.error(f"DSR error {os.path.basename(file_path)}: {e}")


def run():
    log.info("=== SFTP Pull Started ===")

    try:
        sftp, transport = connect_sftp()
    except Exception as e:
        log.error(f"Connection failed: {e}")
        return

    try:
        new_cdr = pull_cdr_files(sftp)
        new_dsr = pull_dsr_files(sftp)
    finally:
        sftp.close()
        transport.close()
        log.info("SFTP connection closed.")

    ingest_cdr_files(new_cdr)
    ingest_dsr_files(new_dsr)

    log.info(f"=== Done | CDR: {len(new_cdr)} | DSR: {len(new_dsr)} ===")


if __name__ == "__main__":
    run()
