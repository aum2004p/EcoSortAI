"""
EcoSort AI - Waste Prediction Module (Time Series ML)
=======================================================
Uses historical scan data to predict future waste generation.

Implements two approaches:
  1. Linear Regression — fits a trend line to daily waste counts.
  2. Simple Moving Average — uses recent average as baseline prediction.

These are lightweight methods suitable for CPU-only deployment without
requiring a separate training step. The prediction runs on-the-fly using
accumulated scan data from the database.

For the LSTM approach (Optional Scope), the structure is outlined in the
report but not implemented here to keep the core scope manageable.
"""

import math
from datetime import datetime, timedelta
from collections import defaultdict


class WastePredictor:
    """Predict future waste amounts from historical scan data."""

    def __init__(self):
        pass

    def _aggregate_daily(self, records):
        """
        Aggregate scan records into daily totals.

        Returns a sorted list of (date_str, total_items) tuples.
        """
        daily = defaultdict(lambda: {'items': 0, 'clean': 0,
                                      'contaminated': 0, 'scans': 0})
        for r in records:
            key = r.created_at.strftime('%Y-%m-%d')
            daily[key]['items'] += r.total_items
            daily[key]['clean'] += r.clean_count
            daily[key]['contaminated'] += r.contaminated_count
            daily[key]['scans'] += 1

        sorted_keys = sorted(daily.keys())
        return [(k, daily[k]) for k in sorted_keys]

    def _linear_regression(self, x_values, y_values):
        """
        Simple linear regression: y = a*x + b.
        Returns (slope, intercept).
        """
        n = len(x_values)
        if n == 0:
            return (0, 0)
        if n == 1:
            return (0, y_values[0])

        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return (0, sum_y / n)

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        return (slope, intercept)

    def predict(self, records, days_ahead=7):
        """
        Predict waste generation for the next N days.

        Args:
            records: list of ScanRecord objects (historical data).
            days_ahead: number of days to predict.

        Returns:
            dict with:
                historical: list of {date, items, clean, contaminated}
                predictions: list of {date, predicted_items, method}
                trend: 'increasing', 'decreasing', or 'stable'
                avg_daily: average daily waste items
                confidence: 'low' | 'medium' | 'high' based on data volume
        """
        daily_data = self._aggregate_daily(records)

        if len(daily_data) == 0:
            return {
                'historical': [],
                'predictions': [],
                'trend': 'no_data',
                'avg_daily': 0,
                'confidence': 'none',
                'message': 'ยังไม่มีข้อมูลเพียงพอสำหรับการพยากรณ์',
            }

        # Build x (day index) and y (items) arrays
        x_values = list(range(len(daily_data)))
        y_values = [d[1]['items'] for d in daily_data]

        # Linear regression
        slope, intercept = self._linear_regression(x_values, y_values)

        # Moving average of last 7 days (or all if fewer)
        recent_window = min(7, len(y_values))
        recent_avg = sum(y_values[-recent_window:]) / recent_window

        # Generate predictions
        predictions = []
        last_date_str = daily_data[-1][0]
        last_date = datetime.strptime(last_date_str, '%Y-%m-%d')

        for i in range(1, days_ahead + 1):
            pred_date = last_date + timedelta(days=i)
            pred_date_str = pred_date.strftime('%Y-%m-%d')

            # Linear regression prediction
            lr_pred = max(0, slope * (len(daily_data) + i - 1) + intercept)

            # Blend: weight recent average more for short-term,
            # use linear regression for longer-term trend
            if i <= 3:
                # Short-term: 60% recent avg, 40% regression
                blended = 0.6 * recent_avg + 0.4 * lr_pred
            else:
                # Longer-term: 30% recent avg, 70% regression
                blended = 0.3 * recent_avg + 0.7 * lr_pred

            predictions.append({
                'date': pred_date_str,
                'label': pred_date.strftime('%d %b'),
                'predicted_items': round(blended, 1),
                'lr_prediction': round(lr_pred, 1),
                'method': 'blended (MA + Linear Regression)',
            })

        # Determine trend
        if slope > 0.1:
            trend = 'increasing'
        elif slope < -0.1:
            trend = 'decreasing'
        else:
            trend = 'stable'

        # Confidence based on data volume
        total_records = len(records)
        if total_records >= 50:
            confidence = 'high'
        elif total_records >= 15:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Historical data for chart
        historical = []
        for date_str, counts in daily_data:
            d = datetime.strptime(date_str, '%Y-%m-%d')
            historical.append({
                'date': date_str,
                'label': d.strftime('%d %b'),
                'items': counts['items'],
                'clean': counts['clean'],
                'contaminated': counts['contaminated'],
                'scans': counts['scans'],
            })

        avg_daily = sum(y_values) / len(y_values)

        return {
            'historical': historical,
            'predictions': predictions,
            'trend': trend,
            'avg_daily': round(avg_daily, 1),
            'confidence': confidence,
            'slope': round(slope, 4),
            'total_data_points': len(daily_data),
        }

    def predict_by_category(self, records, days_ahead=7):
        """
        Predict future waste generation broken down by category.

        Uses the same linear regression approach but per category.
        """
        from models.database import DetectedItem

        # This would need a join query - for simplicity, we aggregate
        # from the records' items
        category_daily = defaultdict(lambda: defaultdict(int))

        for r in records:
            date_key = r.created_at.strftime('%Y-%m-%d')
            for item in r.items:
                category_daily[item.category][date_key] += 1

        result = {}
        for category, daily_counts in category_daily.items():
            sorted_dates = sorted(daily_counts.keys())
            x_values = list(range(len(sorted_dates)))
            y_values = [daily_counts[d] for d in sorted_dates]

            if len(y_values) < 2:
                result[category] = {
                    'predicted': y_values[-1] if y_values else 0,
                    'trend': 'stable',
                }
                continue

            slope, intercept = self._linear_regression(x_values, y_values)
            last_x = len(sorted_dates) - 1
            pred = max(0, slope * (last_x + days_ahead) + intercept)

            if slope > 0.1:
                trend = 'increasing'
            elif slope < -0.1:
                trend = 'decreasing'
            else:
                trend = 'stable'

            result[category] = {
                'predicted_next_week': round(pred, 1),
                'trend': trend,
                'total_so_far': sum(y_values),
            }

        return result
