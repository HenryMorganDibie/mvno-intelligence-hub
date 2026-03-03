import os
import pandas as pd
from sqlalchemy import create_engine
import glob
import logging

# 1. Setup Error Logging to a file
logging.basicConfig(
    filename='ingestion_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_URL = "postgresql://postgres@localhost:5432/mvno_usage_db"
INPUT_DIR = os.path.expanduser("~/mvno-intelligence-hub/data/raw/usage_reports/")

def run_bulk_ingestion():
    engine = create_engine(DB_URL)
    # We only target DATA files for this specific table
    files = glob.glob(os.path.join(INPUT_DIR, "DAILY_97_*_DATA_*.csv"))
    print(f"🚀 Starting ingestion of {len(files)} files...")

    all_data = []
    success_count = 0
    error_count = 0

    for file_path in sorted(files):
        # Skip empty files
        if os.path.getsize(file_path) == 0:
            continue
            
        try:
            # Read headerless CSV
            df = pd.read_csv(file_path, header=None, quotechar='"', on_bad_lines='skip')
            
            # Mapping based on your sample:
            # 2=MSISDN, 6=Time, 27=Upload, 28=Download
            subset = df[[2, 6, 27, 28]].copy()
            subset.columns = ['msisdn', 'usage_time', 'bytes_up', 'bytes_down']
            
            # CLEANING: Ensure bytes are numbers. If it's an IP (like 10.211...), it becomes NaN then 0.
            subset['bytes_up'] = pd.to_numeric(subset['bytes_up'], errors='coerce').fillna(0)
            subset['bytes_down'] = pd.to_numeric(subset['bytes_down'], errors='coerce').fillna(0)
            
            all_data.append(subset)
            success_count += 1
            
            # Batch insert every 100 files
            if len(all_data) >= 100:
                pd.concat(all_data).to_sql('daily_usage', engine, if_exists='append', index=False)
                all_data = []
                print(f"✅ Processed {success_count} files...")

        except Exception as e:
            error_count += 1
            logging.error(f"Failed file: {os.path.basename(file_path)} | Error: {str(e)}")

    # Final batch
    if all_data:
        pd.concat(all_data).to_sql('daily_usage', engine, if_exists='append', index=False)
    
    print(f"\n🏁 FINISHED!")
    print(f"Successfully ingested: {success_count} files")
    print(f"Errors encountered: {error_count} (Details in ingestion_errors.log)")

if __name__ == "__main__":
    run_bulk_ingestion()
