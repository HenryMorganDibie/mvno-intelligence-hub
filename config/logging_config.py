import logging
import os
from dotenv import load_dotenv

load_dotenv()

def setup_logging(module_name):
    # Get level from .env, default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    logger = logging.getLogger(module_name)
    
    # Avoid duplicate handlers if setup_logging is called multiple times
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Stream Handler (Terminal)
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        logger.setLevel(getattr(logging, log_level))
        
    return logger