from pathlib import Path

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
except ImportError:  # statsmodels is optional for this one method.
    SimpleExpSmoothing = None


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "outputs" / "forecast"
DEMAND_STATUSES = {"completed", "delivered", "pending"}
BASELINE_METHODS = ("naive", "moving_average", "exponential_smoothing")
FORECAST_COLUMNS = [
    "product_id",
    "product_name",
    "product_group",
    "record_type",
    "week_start",
    "actual_quantity_kg",
    "forecast_quantity_kg",
    "method",
]
METRIC_COLUMNS = [
    "product_id",
    "product_name",
    "product_group",
    "method",
    "mae",
    "wape",
    "test_weeks",
    "history_weeks",
    "forecast_horizon_weeks",
]


def _validate_horizon(horizon):
    if horizon < 1:
        raise ValueError("horizon must be at least 1.")


def _normalize_methods(methods):
    if isinstance(methods, str):
        methods = (methods,)

    methods = tuple(methods)
    if not methods:
        raise ValueError("methods must include at least one forecast method.")

    invalid_methods = sorted(set(methods).difference(BASELINE_METHODS))
    if invalid_methods:
        valid_methods = ", ".join(BASELINE_METHODS)
        raise ValueError(
            f"Unsupported forecast methods: {invalid_methods}. "
            f"Valid methods are: {valid_methods}."
        )

    return methods


def _prepare_series(series):
    clean = pd.Series(series).copy()
    clean = clean.dropna().astype(float).sort_index()
    if clean.empty:
        raise ValueError("Cannot forecast an empty series.")
    return clean


def _future_index(series, horizon):
    last_index = series.index[-1]
    if isinstance(last_index, pd.Timestamp):
        return pd.date_range(
            start=last_index + pd.Timedelta(days=7),
            periods=horizon,
            freq="7D",
            name=series.index.name,
        )
    return pd.RangeIndex(start=len(series), stop=len(series) + horizon)


def _filter_demand_orders(orders):
    required_columns = {"order_date", "quantity_kg", "product_id"}
    missing_columns = required_columns.difference(orders.columns)
    if missing_columns:
        raise ValueError(f"orders is missing required columns: {sorted(missing_columns)}")

    demand_orders = orders.copy()
    demand_orders["order_date"] = pd.to_datetime(demand_orders["order_date"], errors="raise")

    if "status" in demand_orders.columns:
        demand_orders = demand_orders[demand_orders["status"].isin(DEMAND_STATUSES)]

    return demand_orders


def aggregate_weekly_demand(orders, product_id=None):
    """Aggregate order quantity into Saturday-starting weekly demand."""
    demand_orders = _filter_demand_orders(orders)

    if product_id is not None:
        demand_orders = demand_orders[demand_orders["product_id"] == product_id]

    if demand_orders.empty:
        return pd.Series(dtype=float, name="quantity_kg")

    demand_orders = demand_orders.copy()
    demand_orders["week_start"] = demand_orders["order_date"].dt.to_period("W-FRI").dt.start_time

    weekly = demand_orders.groupby("week_start")["quantity_kg"].sum().sort_index()
    full_index = pd.date_range(
        weekly.index.min(),
        weekly.index.max(),
        freq="7D",
        name="week_start",
    )
    weekly = weekly.reindex(full_index, fill_value=0).astype(float)
    weekly.name = "quantity_kg"
    return weekly


def naive_forecast(series, horizon=8):
    _validate_horizon(horizon)
    clean = _prepare_series(series)
    values = np.repeat(clean.iloc[-1], horizon)
    return pd.Series(values, index=_future_index(clean, horizon), name="forecast_quantity_kg")


def moving_average_forecast(series, window=4, horizon=8):
    _validate_horizon(horizon)
    if window < 1:
        raise ValueError("window must be at least 1.")

    clean = _prepare_series(series)
    effective_window = min(window, len(clean))
    forecast_value = clean.tail(effective_window).mean()
    values = np.repeat(forecast_value, horizon)
    return pd.Series(values, index=_future_index(clean, horizon), name="forecast_quantity_kg")


def exponential_smoothing_forecast(series, horizon=8):
    _validate_horizon(horizon)
    clean = _prepare_series(series)

    if SimpleExpSmoothing is None:
        raise ImportError(
            "statsmodels is required for exponential_smoothing_forecast. "
            "Install requirements.txt or use naive/moving_average instead."
        )

    if len(clean) < 2:
        return naive_forecast(clean, horizon=horizon)

    model = SimpleExpSmoothing(clean.to_numpy(), initialization_method="estimated")
    fitted_model = model.fit(optimized=True)
    values = np.maximum(fitted_model.forecast(horizon), 0)
    return pd.Series(values, index=_future_index(clean, horizon), name="forecast_quantity_kg")


def calculate_mae(actual, forecast):
    actual_values = pd.Series(actual).astype(float).to_numpy()
    forecast_values = pd.Series(forecast).astype(float).to_numpy()

    if len(actual_values) != len(forecast_values):
        raise ValueError("actual and forecast must have the same length.")

    return float(np.mean(np.abs(actual_values - forecast_values)))


def calculate_wape(actual, forecast):
    actual_values = pd.Series(actual).astype(float).to_numpy()
    forecast_values = pd.Series(forecast).astype(float).to_numpy()

    if len(actual_values) != len(forecast_values):
        raise ValueError("actual and forecast must have the same length.")

    total_actual = np.sum(np.abs(actual_values))
    if total_actual == 0:
        return np.nan

    return float(np.sum(np.abs(actual_values - forecast_values)) / total_actual)


def _run_method(series, method, horizon, window=4):
    if method == "naive":
        return naive_forecast(series, horizon=horizon)
    if method == "moving_average":
        return moving_average_forecast(series, window=window, horizon=horizon)
    if method == "exponential_smoothing":
        return exponential_smoothing_forecast(series, horizon=horizon)
    valid_methods = ", ".join(BASELINE_METHODS)
    raise ValueError(f"method must be one of: {valid_methods}.")


def backtest_forecast(series, method="moving_average", window=4):
    clean = _prepare_series(series)
    if len(clean) < 3:
        raise ValueError("At least 3 weekly observations are required for backtesting.")

    test_size = min(8, max(1, len(clean) // 4))
    train = clean.iloc[:-test_size]
    actual = clean.iloc[-test_size:]

    if train.empty:
        raise ValueError("Not enough history to create a train/test split.")

    forecast = _run_method(train, method=method, horizon=test_size, window=window)
    forecast.index = actual.index

    return {
        "method": method,
        "test_size": test_size,
        "actual": actual,
        "forecast": forecast,
        "mae": calculate_mae(actual, forecast),
        "wape": calculate_wape(actual, forecast),
    }


def get_backtest_predictions(series, method="moving_average", window=4):
    backtest = backtest_forecast(series, method=method, window=window)

    return pd.DataFrame(
        {
            "week_start": backtest["actual"].index,
            "actual_demand": backtest["actual"].to_numpy(),
            "forecast_demand": backtest["forecast"].to_numpy(),
            "method": backtest["method"],
        }
    )


def forecast_all_products(orders, products, horizon=8, methods=BASELINE_METHODS):
    _validate_horizon(horizon)
    methods = _normalize_methods(methods)
    required_product_columns = {"product_id", "product_name", "product_group"}
    missing_columns = required_product_columns.difference(products.columns)
    if missing_columns:
        raise ValueError(f"products is missing required columns: {sorted(missing_columns)}")

    forecast_rows = []
    metric_rows = []

    for product in products.sort_values("product_id").itertuples(index=False):
        weekly = aggregate_weekly_demand(orders, product_id=product.product_id)
        product_info = {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "product_group": product.product_group,
        }

        if weekly.empty:
            for method in methods:
                metric_rows.append(
                    {
                        **product_info,
                        "method": method,
                        "mae": np.nan,
                        "wape": np.nan,
                        "test_weeks": 0,
                        "history_weeks": 0,
                        "forecast_horizon_weeks": horizon,
                    }
                )
            continue

        for week_start, quantity_kg in weekly.items():
            forecast_rows.append(
                {
                    **product_info,
                    "record_type": "actual",
                    "week_start": week_start,
                    "actual_quantity_kg": quantity_kg,
                    "forecast_quantity_kg": np.nan,
                    "method": "historical",
                }
            )

        for method in methods:
            backtest = backtest_forecast(weekly, method=method)
            forecast = _run_method(weekly, method=method, horizon=horizon)

            for week_start, quantity_kg in forecast.items():
                forecast_rows.append(
                    {
                        **product_info,
                        "record_type": "forecast",
                        "week_start": week_start,
                        "actual_quantity_kg": np.nan,
                        "forecast_quantity_kg": quantity_kg,
                        "method": method,
                    }
                )

            metric_rows.append(
                {
                    **product_info,
                    "method": backtest["method"],
                    "mae": backtest["mae"],
                    "wape": backtest["wape"],
                    "test_weeks": backtest["test_size"],
                    "history_weeks": len(weekly),
                    "forecast_horizon_weeks": horizon,
                }
            )

    forecast_df = pd.DataFrame(forecast_rows, columns=FORECAST_COLUMNS)
    metrics_df = pd.DataFrame(metric_rows, columns=METRIC_COLUMNS)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    forecast_df.to_csv(OUTPUT_DIR / "product_forecasts.csv", index=False)
    metrics_df.to_csv(OUTPUT_DIR / "forecast_metrics.csv", index=False)

    return forecast_df, metrics_df
