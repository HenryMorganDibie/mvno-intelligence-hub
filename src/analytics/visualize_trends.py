import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# Database Connection
DB_URL = "postgresql://postgres@localhost:5432/mvno_usage_db"
engine = create_engine(DB_URL)

def generate_hourly_chart():
    query = """
    SELECT 
        EXTRACT(HOUR FROM usage_time) as hour,
        SUM(bytes_up + bytes_down) / 1024.0 / 1024.0 as total_mb
    FROM daily_usage 
    GROUP BY hour 
    ORDER BY hour;
    """
    
    # Load data into a DataFrame
    df = pd.read_sql(query, engine)
    
    # Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(df['hour'], df['total_mb'], marker='o', linestyle='-', color='#1f77b4')
    
    plt.title('Network Traffic Trend (Hourly)', fontsize=14)
    plt.xlabel('Hour of Day (24h)', fontsize=12)
    plt.ylabel('Total MB Consumed', fontsize=12)
    plt.xticks(range(0, 24))
    plt.grid(True, alpha=0.3)
    
    # Save the file
    plt.savefig('hourly_traffic_trend.png')
    print("🚀 Chart saved as 'hourly_traffic_trend.png'")

if __name__ == "__main__":
    generate_hourly_chart()
