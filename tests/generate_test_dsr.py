import csv
import random
from datetime import datetime, timedelta

def generate_fake_dsr(filename, num_records=100):
    # Field list derived from DSR Layout 
    # Note: We omit headers in the file as per spec [cite: 71]
    
    with open(filename, mode='w', newline='') as f:
        for _ in range(num_records):
            msisdn = f"202{random.randint(1000000, 9999999)}"
            usage_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Simulate some 'NO CDR FOUND' entries as per spec 
            has_usage = random.choice([True, True, False])
            flag = "CURRENT_CDR" if has_usage else "NO CDR FOUND"
            gprs = f"{random.uniform(1000, 5000000):.3f}" if has_usage else "0.00"
            
            row = [
                usage_date, msisdn, "310240" + str(random.randint(10**8, 10**9-1)),
                "0", "00000001", "1", "0", "0.00", "0", gprs, 
                flag, "ACTIVE", "2023-01-01 10:00:00", "", "", 
                "1004", "2026-12-31", "890124" + str(random.randint(10**12, 10**13-1)),
                "90210"
            ]
            
            # Format as CSV but terminate with semicolon+newline [cite: 73]
            line = ",".join(f'"{item}"' if item else '""' for item in row)
            f.write(f"{line};\n")

if __name__ == "__main__":
    generate_fake_dsr("data/samples/DSR_Sample_20260201.csv")
    print("✅ Synthetic DSR generated with semicolon terminators.")