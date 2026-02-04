"""
Current Month Usage Predictor
Predicts total usage by end of current billing cycle using Prophet.
Production-ready: Uses centralized logging, database, and env settings.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from prophet import Prophet
from sqlalchemy import text
import pickle

# 1. Professional Imports
from config.logging_config import setup_logging
from config.database import engine

# Initialize professional logger
logger = setup_logging(__name__)

# 2. Silence Prophet/CmdStanPy noise for a clean production output
import logging
logging.getLogger('prophet').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

class CurrentMonthPredictor:
    """
    Predicts end-of-month data usage for subscribers
    Uses Prophet for time-series forecasting
    """
    
    def __init__(self, msisdn, model_dir='models'):
        self.model = None
        self.msisdn = msisdn
        self.model_path = os.path.join(model_dir, f'{msisdn}_prophet.pkl')
        self.confidence_level = 0.90  # Matches .env CONFIDENCE_LEVEL
        
    def prepare_training_data(self, lookback_months=3):
        """Fetch historical usage from daily aggregates"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_months * 30)
        
        query = text("""
            SELECT 
                usage_date as ds,
                data_bytes / 1073741824.0 as y
            FROM usage_daily_agg
            WHERE msisdn = :msisdn
            AND usage_date >= :start_date
            AND usage_date <= :end_date
            ORDER BY usage_date
        """)
        
        try:
            with engine.connect() as conn:
                df = pd.read_sql(query, conn, params={
                    'msisdn': self.msisdn,
                    'start_date': start_date,
                    'end_date': end_date
                })
                
                if df.empty:
                    logger.warning(f"No historical data found for {self.msisdn}")
                    return None
                
                df['ds'] = pd.to_datetime(df['ds'])
                
                # Fill missing dates with 0 to maintain time-series continuity
                date_range = pd.date_range(start=df['ds'].min(), end=df['ds'].max(), freq='D')
                df_complete = pd.DataFrame({'ds': date_range})
                df = df_complete.merge(df, on='ds', how='left').fillna(0)
                
                logger.info(f"Prepared {len(df)} days of training data for {self.msisdn}")
                return df
                
        except Exception as e:
            logger.error(f"Error preparing training data for {self.msisdn}: {e}")
            return None
    
    def train(self, lookback_months=3):
        """Train Prophet model on subscriber history"""
        df = self.prepare_training_data(lookback_months)
        
        if df is None or len(df) < 2:
            logger.warning(f"Insufficient data for {self.msisdn} (minimum 2 days required)")
            return False
        
        try:
            # Enable weekly seasonality only if we have at least a week of data
            has_enough_for_weekly = len(df) >= 7

            self.model = Prophet(
                interval_width=self.confidence_level,
                daily_seasonality=False,
                weekly_seasonality=has_enough_for_weekly,
                yearly_seasonality=False,
                changepoint_prior_scale=0.05
            )
            
            self.model.fit(df)
            logger.info(f"Successfully trained model for {self.msisdn}")
            return True
            
        except Exception as e:
            logger.error(f"Error training model for {self.msisdn}: {e}")
            return False
    
    def predict_month_end(self, current_usage_gb, days_remaining):
        """Generate forecast for the remainder of the billing cycle"""
        if self.model is None:
            logger.error(f"Model not trained for {self.msisdn}")
            return None
        
        if days_remaining <= 0:
            return self._zero_days_result(current_usage_gb)

        future = self.model.make_future_dataframe(periods=days_remaining, freq='D')
        
        try:
            forecast = self.model.predict(future)
            remaining_predictions = forecast.tail(days_remaining)
            
            # Sum predicted usage for remaining days
            predicted_additional_gb = max(0, remaining_predictions['yhat'].sum())
            predicted_total_gb = current_usage_gb + predicted_additional_gb
            
            # Get confidence intervals
            predicted_additional_lower = max(0, remaining_predictions['yhat_lower'].sum())
            predicted_additional_upper = max(0, remaining_predictions['yhat_upper'].sum())
            
            result = {
                'msisdn': self.msisdn,
                'current_usage_gb': round(current_usage_gb, 2),
                'predicted_total_gb': round(predicted_total_gb, 2),
                'predicted_additional_gb': round(predicted_additional_gb, 2),
                'confidence_lower_gb': round(current_usage_gb + predicted_additional_lower, 2),
                'confidence_upper_gb': round(current_usage_gb + predicted_additional_upper, 2),
                'days_remaining': days_remaining,
                'predicted_at': datetime.now().isoformat()
            }
            return result
            
        except Exception as e:
            logger.error(f"Error making prediction for {self.msisdn}: {e}")
            return None

    def _zero_days_result(self, usage):
        return {
            'msisdn': self.msisdn, 'current_usage_gb': round(usage, 2),
            'predicted_total_gb': round(usage, 2), 'predicted_additional_gb': 0.0,
            'confidence_lower_gb': round(usage, 2), 'confidence_upper_gb': round(usage, 2),
            'days_remaining': 0, 'predicted_at': datetime.now().isoformat()
        }

    def save_model(self):
        if self.model is None: return False
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            return True
        except Exception as e:
            logger.error(f"Error saving model for {self.msisdn}: {e}")
            return False

    def load_model(self):
        if not os.path.exists(self.model_path): return False
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            return True
        except Exception as e:
            logger.error(f"Error loading model for {self.msisdn}: {e}")
            return False

def predict_for_subscriber(msisdn, retrain=False):
    """Wrapper to handle the full prediction workflow for a single MSISDN"""
    from src.features.usage_aggregation import get_subscriber_usage_summary
    
    summary = get_subscriber_usage_summary(msisdn)
    if not summary:
        return None
    
    current_usage_gb = summary['usage_mtd']['data_gb']
    cycle_end = datetime.strptime(summary['billing_cycle']['end'], '%Y-%m-%d').date()
    days_remaining = max(0, (cycle_end - datetime.now().date()).days)
    
    predictor = CurrentMonthPredictor(msisdn)
    
    if retrain or not predictor.load_model():
        if not predictor.train(lookback_months=3):
            return None
        predictor.save_model()
    
    return predictor.predict_month_end(current_usage_gb, days_remaining)

def save_prediction_to_db(prediction):
    """Saves result to predictions_current_month with upsert logic"""
    if not prediction: return False
    
    query = text("""
        INSERT INTO predictions_current_month (
            msisdn, billing_month, prediction_date,
            predicted_data_gb, confidence_lower_gb, confidence_upper_gb,
            days_remaining, current_usage_gb, model_version
        ) VALUES (
            :msisdn, :billing_month, :prediction_date,
            :predicted_data_gb, :confidence_lower_gb, :confidence_upper_gb,
            :days_remaining, :current_usage_gb, :model_version
        )
        ON CONFLICT (msisdn, billing_month, prediction_date)
        DO UPDATE SET
            predicted_data_gb = EXCLUDED.predicted_data_gb,
            confidence_lower_gb = EXCLUDED.confidence_lower_gb,
            confidence_upper_gb = EXCLUDED.confidence_upper_gb,
            days_remaining = EXCLUDED.days_remaining,
            current_usage_gb = EXCLUDED.current_usage_gb,
            updated_at = NOW()
    """)
    
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                'msisdn': prediction['msisdn'],
                'billing_month': billing_start.strftime('%Y-%m-%d'),
                'prediction_date': datetime.now().date(),
                'predicted_data_gb': float(prediction['predicted_total_gb']),
                'confidence_lower_gb': float(prediction['confidence_lower_gb']),
                'confidence_upper_gb': float(prediction['confidence_upper_gb']),
                'days_remaining': int(prediction['days_remaining']),
                'current_usage_gb': float(prediction['current_usage_gb']),
                'model_version': 'prophet_v1'
            })
        logger.info(f"Saved prediction for {prediction['msisdn']} to database")
        return True
    except Exception as e:
        logger.error(f"Error saving prediction for {prediction['msisdn']}: {e}")
        return False

if __name__ == "__main__":
    test_msisdn = "2026853028"
    logger.info(f"Running Current Month Predictor Test for {test_msisdn}")
    
    result = predict_for_subscriber(test_msisdn, retrain=True)
    
    if result:
        print("\n" + "="*50)
        print(f"PREDICTION RESULTS: {test_msisdn}")
        print(f"Expected Usage: {result['predicted_total_gb']:.2f} GB")
        print(f"Confidence Upper: {result['confidence_upper_gb']:.2f} GB")
        print(f"Days Left: {result['days_remaining']}")
        print("="*50 + "\n")
        save_prediction_to_db(result)