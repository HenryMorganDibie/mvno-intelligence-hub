import os
from dotenv import load_dotenv
from pathlib import Path

# Load variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database Configuration (Pulled from .env)
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "mvno_usage_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

# Tier Caps (Pulled from .env)
TIERS = {
    "tier_1": {"cap": float(os.getenv("TIER_1_CAP_GB", 5.0)), "cost": float(os.getenv("TIER_1_COST", 15.0))},
    "tier_2": {"cap": float(os.getenv("TIER_2_CAP_GB", 10.0)), "cost": float(os.getenv("TIER_2_COST", 25.0))},
    "tier_3": {"cap": float(os.getenv("TIER_3_CAP_GB", 20.0)), "cost": float(os.getenv("TIER_3_COST", 40.0))},
}

# Paths
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)