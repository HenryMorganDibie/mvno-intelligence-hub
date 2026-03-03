"""
Next Month Usage Predictor
Predicts total usage for the upcoming billing cycle using Prophet.
Used for donation planning — helps subscribers know how much they can donate next month.
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from prophet import Prophet
from sqlalchemy import text
import pickle

from config.logging_config import setup_logging
from config.database import engine

logger = setup_logging(__name__)

import logging
logging.getLogger('prophet').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)


class NextMonthPredictor:
    """
    Predicts next billing cycle data usage for donation planning.
    """

    def __init__(self, msisdn, model_dir='models'):
        self.model = None
        self.msisdn = msisdn
        self.model_path = os.path.join(model_dir, f'{msisdn}_next_month_prophet.pkl')
        self.confidence_level = 0.90

    def prepare_training_data(self, lookback_months=3):
        """Fetch historical usage from daily_usage"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_months * 30)

        query = text("""
            SELECT
                date_trunc('day', usage_time) as ds,
                SUM(bytes_up + bytes_down) / 1073741824.0 as y
            FROM daily_usage
            WHERE msisdn = :msisdn
            AND usage_time::date >= :start_date
            AND usage_time::date <= :end_date
            GROUP BY 1 ORDER BY 1
        """)

        try:
            with engine.connect() as conn:
                df = pd.read_sql(query, conn, params={
                    'msisdn': str(self.msisdn),
                    'start_date': start_date,
                    'end_date': end_date
                })

                if df.empty:
                    logger.warning(f"No historical data for next month predictor: {self.msisdn}")
                    return None

                df['ds'] = pd.to_datetime(df['ds']).dt.tz_localize(None)

                date_range = pd.date_range(start=df['ds'].min(), end=df['ds'].max(), freq='D')
                df_complete = pd.DataFrame({'ds': date_range})
                df = df_complete.merge(df, on='ds', how='left').fillna(0)

                logger.info(f"Prepared {len(df)} days for next month prediction: {self.msisdn}")
                return df

        except Exception as e:
            logger.error(f"Error preparing next month training data for {self.msisdn}: {e}")
            return None

    def train(self, lookback_months=3):
        """Train Prophet model"""
        df = self.prepare_training_data(lookback_months)

        if df is None or len(df) < 2:
            logger.warning(f"Insufficient data for next month predictor: {self.msisdn}")
            return False

        try:
            self.model = Prophet(
                interval_width=self.confidence_level,
                daily_seasonality=False,
                weekly_seasonality=len(df) >= 7,
                yearly_seasonality=False,
                changepoint_prior_scale=0.05
            )
            self.model.fit(df)
            logger.info(f"Next month model trained for {self.msisdn}")
            return True

        except Exception as e:
            logger.error(f"Error training next month model for {self.msisdn}: {e}")
            return False

    def predict_next_month(self):
        """Forecast the full next billing cycle (30 days)"""
        if self.model is None:
            logger.error(f"Next month model not trained for {self.msisdn}")
            return None

        today = datetime.now().date()
        next_cycle_days = 30

        try:
            future = self.model.make_future_dataframe(periods=next_cycle_days + 30, freq='D')
            forecast = self.model.predict(future)

            next_month_forecast = forecast[
                forecast['ds'].dt.date > today
            ].head(next_cycle_days)

            predicted_gb = max(0, next_month_forecast['yhat'].sum())
            predicted_lower = max(0, next_month_forecast['yhat_lower'].sum())
            predicted_upper = max(0, next_month_forecast['yhat_upper'].sum())

            result = {
                'msisdn': str(self.msisdn),
                'predicted_next_month_gb': round(predicted_gb, 2),
                'confidence_lower_gb': round(predicted_lower, 2),
                'confidence_upper_gb': round(predicted_upper, 2),
                'forecast_days': next_cycle_days,
                'predicted_at': datetime.now().isoformat()
            }
            return result

        except Exception as e:
            logger.error(f"Error predicting next month for {self.msisdn}: {e}")
            return None

    def save_model(self):
        if self.model is None:
            return False
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            return True
        except Exception as e:
            logger.error(f"Error saving next month model for {self.msisdn}: {e}")
            return False

    def load_model(self):
        if not os.path.exists(self.model_path):
            return False
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            return True
        except Exception as e:
            logger.error(f"Error loading next month model for {self.msisdn}: {e}")
            return False


def predict_next_month_for_subscriber(msisdn, retrain=False):
    """Wrapper for full next month prediction workflow"""
    predictor = NextMonthPredictor(msisdn)

    if retrain or not predictor.load_model():
        if not predictor.train(lookback_months=3):
            logger.error(f"Failed to train next month model for {msisdn}")
            return None
        predictor.save_model()

    return predictor.predict_next_month()


def save_next_month_prediction_to_db(prediction):
    """Save next month prediction to predictions_next_month table"""
    if not prediction:
        return False

    from src.features.usage_aggregation import get_current_billing_cycle_dates
    billing_start, billing_end = get_current_billing_cycle_dates()

    if billing_end.month == 12:
        next_billing_month = billing_end.replace(year=billing_end.year + 1, month=1, day=21)
    else:
        next_billing_month = billing_end.replace(month=billing_end.month + 1, day=21)

    query = text("""
        INSERT INTO predictions_next_month (
            msisdn, current_month, next_month,
            predicted_data_gb, confidence_lower_gb, confidence_upper_gb,
            model_version
        ) VALUES (
            :msisdn, :current_month, :next_month,
            :predicted_data_gb, :confidence_lower_gb, :confidence_upper_gb,
            :model_version
        )
        ON CONFLICT (msisdn, next_month)
        DO UPDATE SET
            predicted_data_gb = EXCLUDED.predicted_data_gb,
            confidence_lower_gb = EXCLUDED.confidence_lower_gb,
            confidence_upper_gb = EXCLUDED.confidence_upper_gb
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, {
                'msisdn': prediction['msisdn'],
                'current_month': billing_start,
                'next_month': next_billing_month,
                'predicted_data_gb': float(prediction['predicted_next_month_gb']),
                'confidence_lower_gb': float(prediction['confidence_lower_gb']),
                'confidence_upper_gb': float(prediction['confidence_upper_gb']),
                'model_version': 'prophet_v1'
            })
        logger.info(f"Saved next month prediction for {prediction['msisdn']}")
        return True
    except Exception as e:
        logger.error(f"Error saving next month prediction for {prediction['msisdn']}: {e}")
        return False


if __name__ == "__main__":
    test_msisdn = "4042778501"
    logger.info(f"Testing Next Month Predictor for {test_msisdn}")

    result = predict_next_month_for_subscriber(test_msisdn, retrain=True)
    if result:
        print("\n" + "="*50)
        print(f"NEXT MONTH PREDICTION: {test_msisdn}")
        print(f"Predicted Usage: {result['predicted_next_month_gb']:.2f} GB")
        print(f"Lower Bound:     {result['confidence_lower_gb']:.2f} GB")
        print(f"Upper Bound:     {result['confidence_upper_gb']:.2f} GB")
        print("="*50 + "\n")
        save_next_month_prediction_to_db(result)
