import os

import pandas as pd

from sqlalchemy import create_engine



# 1. Database Connection

# Replace 'password' with your actual PostgreSQL password

DB_URL = "postgresql://postgres@localhost:5432/mvno_usage_db"

engine = create_engine(DB_URL)



# 2. Path to your raw data (standardizing based on your structure)

INPUT_DIR = "data/raw/subscriber_reports/"



def run_ingestion():

    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".csv")]

    print(f"🚀 Found {len(files)} reports. Starting TimescaleDB ingestion...")



    for file in sorted(files):

        file_path = os.path.join(INPUT_DIR, file)

        

        # Load the CSV

        df = pd.read_csv(file_path)

        

        # MAPPING: Match CSV headers to your SQL Schema

        # The CSV has 'GPRS', but your table wants 'data_bytes'

        # The CSV has 'VOICE', but your table wants 'voice_minutes'

        mapping = {

            'USAGE_DATE': 'usage_date',

            'MSISDN': 'msisdn',

            'IMSI': 'imsi',

            'TENANT_ID': 'tenant_id',

            'BILLING_CODE': 'billing_code',

            'ACTIVE_STATUS': 'active_status',

            'SUSPEND_STATUS': 'suspend_status',

            'VOICE': 'voice_minutes',

            'SMS': 'sms_units',

            'GPRS': 'data_bytes',

            'FLAG': 'flag',

            'SUBSCRIBER_STATE': 'subscriber_state',

            'ACTIVATION_DATE': 'activation_date',

            'SUSPEND_DATE': 'suspend_date',

            'DEACTIVATION_DATE': 'deactivation_date',

            'BUNDLE_ID': 'bundle_id',

            'EXPIRATION_DATE': 'expiration_date',

            'ICCID': 'iccid',

            'ZIPCODE': 'zipcode'

        }

        

        df = df.rename(columns=mapping)

        

        # Ensure dates are proper datetime objects

        df['usage_date'] = pd.to_datetime(df['usage_date'])

        

        # Insert into DB

        try:

            # We use 'append' because usage_date + msisdn is your Primary Key

            df.to_sql('daily_subscriber_reports', engine, if_exists='append', index=False)

            print(f"✅ Ingested: {file}")

        except Exception as e:

            if "duplicate key value" in str(e):

                print(f"⏩ Skipping {file} (Data already exists)")

            else:

                print(f"❌ Error in {file}: {e}")



if __name__ == "__main__":

    run_ingestion()
