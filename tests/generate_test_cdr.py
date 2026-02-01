import os
import csv
import random
from datetime import datetime, timedelta

def generate_fake_cdr(filename, num_records=150):
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    usage_types = ["VOICE_MO", "VOICE_MT", "SMS_MO", "SMS_MT", "GPRS"]
    msisdns = ["2026853028", "2024828332", "2026011325", "2024794933"] # Matches our DSR sample

    with open(filename, mode='w', newline='') as f:
        for _ in range(num_records):
            u_type = random.choice(usage_types)
            msisdn = random.choice(msisdns)
            effective_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Base row structure (simplified to match the common start of all CDR types)
            # Schema: ID, Tenant, MSISDN, SubID, UsageType, Network, Date...
            row = [
                random.randint(100000, 999999), # ID
                "0",                            # Tenant
                msisdn,                         # MSISDN
                "60",                           # SubscriberID
                u_type,                         # Usage Type
                "HOME",                         # Network
                effective_date,                 # Date
            ]

            # Add specific columns based on type
            if "VOICE" in u_type:
                # Add voice-specific fields (Duration, Other party, etc.)
                row.extend(["3475551234", "ACCT123", "SEQ123", "IMSI123", "202602011200", "SW01", "IMEI123", "SID1", "SID2", "CELL1", "PLACE", "REG", "OTRUNK", "ITRUNK"])
                row.append(random.randint(1, 15)) # Duration Minutes
                row.append(random.randint(0, 59)) # Duration Seconds
                row.extend(["TC", "1", "TRANS", "PLMN", "USA", "-05:00", "POST", "5G", "UNLIMITED", "SUPP", "BILL01"])
            
            elif "SMS" in u_type:
                # Add SMS-specific fields
                row.extend(["3475551234", "ACCT123", "SEQ123", "IMSI123", "202602011200", "SW01", "IMEI123", "SID1", "SID2", "CELL1", "PLACE", "REG", "OTRUNK", "ITRUNK"])
                row.append(1) # Message Count
                row.extend(["TC", "1", "TRANS", "PLMN", "USA", "-05:00", "POST", "5G", "UNLIMITED", "SUPP", "BILL01"])

            elif u_type == "GPRS":
                # Add Data-specific fields
                row.extend(["", "ACCT123", "SEQ123", "IMSI123", "202602011200", "internet.apn", "IMEI123", "SID1", "SID2", "1.1.1.1", "", "CELL1", "LAC"])
                row.append(round(random.uniform(1024, 5120000), 3)) # Total Volume Bytes
                row.append(random.randint(10, 300)) # Duration
                row.extend(["DESC", "DC", "1", "", "", random.uniform(512, 256000), random.uniform(512, 256000), "PLMN", "USA", "GGSN", "CHG", "01", "ENT", "-05:00", "POST", "5G", "UNLIMITED", "RG", "BILL01"])

            # Format as CSV with semicolon terminator per spec
            line = ",".join(f'"{str(x)}"' for x in row) + ";"
            f.write(line + "\n")

    print(f"✅ Generated synthetic CDR file: {filename}")

if __name__ == "__main__":
    generate_fake_cdr("data/samples/CDR_PartnerID_20260201.csv")