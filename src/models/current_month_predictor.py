"""
Current Month Usage Predictor
Predicts total usage by end of current billing cycle using Prophet
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from prophet import Prophet
from sqlalchemy import text
import logging
import pickle

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database connection
from config.database import engine

class CurrentMonthPredictor:
    """
    Predicts end-of-month data usage for subscribers
    Uses Prophet for time-series forecasting
    """
    
    def __init__(self, model_path='models/current_month_prophet.pkl'):
        self.model = None
        self.model_path = model_path
        self.confidence_level = 0.90  # 90% confidence interval
        
    def prepare_training_data(self, msisdn, lookback_months=3):
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
                    'msisdn': msisdn,
                    'start_date': start_date,
                    'end_date': end_date
                })
                
                if df.empty:
                    logger.warning(f"No historical data found for {msisdn}")
                    return None
                
                df['ds'] = pd.to_datetime(df['ds'])
                
                # Fill missing dates with 0 to maintain time-series continuity
                date_range = pd.date_range(start=df['ds'].min(), end=df['ds'].max(), freq='D')
                df_complete = pd.DataFrame({'ds': date_range})
                df = df_complete.merge(df, on='ds', how='left').fillna(0)
                
                logger.info(f"Prepared {len(df)} days of training data for {msisdn}")
                return df
                
        except Exception as e:
            logger.error(f"Error preparing training data for {msisdn}: {e}")
            return None
    
    def train(self, msisdn, lookback_months=3):
        df = self.prepare_training_data(msisdn, lookback_months)
        
        # Prophet requires at least 2 non-NaN rows to establish a trend
        if df is None or len(df) < 2:
            logger.warning(f"Insufficient data to train model for {msisdn} (minimum 2 days required)")
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
            logger.info(f"Successfully trained model for {msisdn}")
            return True
            
        except Exception as e:
            logger.error(f"Error training model for {msisdn}: {e}")
            return False
    
    def predict_month_end(self, msisdn, current_usage_gb, days_remaining):
        if self.model is None:
            logger.error("Model not trained. Call train() first.")
            return None
        
        # If it's the last day of the cycle, prediction is just current usage
        if days_remaining <= 0:
            return self._zero_days_result(msisdn, current_usage_gb)

        # Create future dataframe for remaining days
        future = self.model.make_future_dataframe(periods=days_remaining, freq='D')
        
        try:
            forecast = self.model.predict(future)
            remaining_predictions = forecast.tail(days_remaining)
            
            # Sum predicted usage for remaining days (ensure no negative daily values)
            predicted_additional_gb = max(0, remaining_predictions['yhat'].sum())
            predicted_total_gb = current_usage_gb + predicted_additional_gb
            
            # Get confidence intervals
            predicted_additional_lower = max(0, remaining_predictions['yhat_lower'].sum())
            predicted_additional_upper = max(0, remaining_predictions['yhat_upper'].sum())
            
            result = {
                'msisdn': msisdn,
                'current_usage_gb': round(current_usage_gb, 2),
                'predicted_total_gb': round(predicted_total_gb, 2),
                'predicted_additional_gb': round(predicted_additional_gb, 2),
                'confidence_lower_gb': round(current_usage_gb + predicted_additional_lower, 2),
                'confidence_upper_gb': round(current_usage_gb + predicted_additional_upper, 2),
                'confidence_level': self.confidence_level,
                'days_remaining': days_remaining,
                'predicted_at': datetime.now().isoformat()
            }
            return result
            
        except Exception as e:
            logger.error(f"Error making prediction for {msisdn}: {e}")
            return None

    def _zero_days_result(self, msisdn, usage):
        return {
            'msisdn': msisdn, 'current_usage_gb': round(usage, 2),
            'predicted_total_gb': round(usage, 2), 'predicted_additional_gb': 0.0,
            'confidence_lower_gb': round(usage, 2), 'confidence_upper_gb': round(usage, 2),
            'confidence_level': self.confidence_level, 'days_remaining': 0,
            'predicted_at': datetime.now().isoformat()
        }

    def save_model(self):
        if self.model is None: return False
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def load_model(self):
        if not os.path.exists(self.model_path): return False
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False


def predict_for_subscriber(msisdn, retrain=False):
    from src.features.usage_aggregation import get_subscriber_usage_summary
    
    summary = get_subscriber_usage_summary(msisdn)
    if not summary:
        logger.error(f"Could not get usage summary for {msisdn}")
        return None
    
    current_usage_gb = summary['usage_mtd']['data_gb']
    
    # FIX: Calculate days_remaining from the cycle end date
    cycle_end_str = summary['billing_cycle']['end']
    cycle_end = datetime.strptime(cycle_end_str, '%Y-%m-%d').date()
    today = datetime.now().date()
    days_remaining = max(0, (cycle_end - today).days)
    
    predictor = CurrentMonthPredictor(model_path=f'models/{msisdn}_current_month.pkl')
    
    if retrain or not predictor.load_model():
        if not predictor.train(msisdn, lookback_months=3):
            return None
        predictor.save_model()
    
    return predictor.predict_month_end(msisdn, current_usage_gb, days_remaining)


def save_prediction_to_db(prediction):
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
            created_at = NOW()
    """)
    
    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, _ = get_current_billing_cycle_dates()
    
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                'msisdn': prediction['msisdn'],
                'billing_month': prediction['billing_month'] if 'billing_month' in prediction else billing_start.strftime('%Y-%m-%d'),
                'prediction_date': datetime.now().date(),
                # FIX: Explicitly cast NumPy types to Python floats/ints
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
        logger.error(f"Error saving prediction to database: {e}")
        return False

if __name__ == "__main__":
    print("Testing Current Month Predictor\n" + "=" * 50)
    test_msisdn = "2026853028"
    prediction = predict_for_subscriber(test_msisdn, retrain=True)
    
    if prediction:
        print("\n✅ Prediction Results:")
        print(f"   Current Usage: {prediction['current_usage_gb']} GB")
        print(f"   Predicted Total: {prediction['predicted_total_gb']} GB")
        print(f"   Additional Usage: {prediction['predicted_additional_gb']} GB")
        print(f"   Confidence Range: {prediction['confidence_lower_gb']} - {prediction['confidence_upper_gb']} GB")
        print(f"   Days Remaining: {prediction['days_remaining']}")
        
        if save_prediction_to_db(prediction):
            print("\n✅ Prediction saved to database")
    else:
        print("\n❌ Prediction failed (Hint: Ensure DB has at least 2 days of data for this MSISDN)")
    print("\n" + "=" * 50)