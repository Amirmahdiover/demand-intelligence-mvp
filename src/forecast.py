from pathlib import Path

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
except ImportError:  # statsmodels is optional for this one method.
    SimpleExpSmoothing = None

try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
except ImportError:  # scikit-learn is optional for the controlled ML candidates.
    GradientBoostingRegressor = None
    RandomForestRegressor = None


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "outputs" / "forecast"
MARKET_FACTORS_PATH = ROOT_DIR / "data" / "market_factors.csv"
DEMAND_STATUSES = {"completed", "delivered", "pending"}
BASELINE_METHODS = ("naive", "moving_average", "exponential_smoothing")
ML_METHODS = ("random_forest", "gradient_boosting")
ML_BASE_FEATURES = (
    "lag_1",
    "lag_2",
    "lag_4",
    "rolling_mean_4",
    "rolling_mean_8",
    "week_of_year",
    "month",
)
MARKET_FACTOR_COLUMNS = (
    "usd_rate",
    "pet_price_index",
    "export_condition_index",
)
FORECAST_COLUMNS = [
    "product_id",
    "product_name",
    "product_group",
    "forecast_period",
    "week_start",
    "record_type",
    "actual_quantity_kg",
    "forecast_quantity_kg",
    "method",
    "selected_method",
    "selected_method_wape",
]
METRIC_COLUMNS = [
    "product_id",
    "product_name",
    "product_group",
    "method",
    "mae",
    "wape",
    "MAE",
    "WAPE",
    "is_selected_method",
    "test_weeks",
    "history_weeks",
    "forecast_horizon_weeks",
]
SELECTED_METHOD_COLUMNS = [
    "product_id",
    "product_name",
    "selected_method",
    "selected_method_mae",
    "selected_method_wape",
    "rating",
]


def get_candidate_methods():
    methods = list(BASELINE_METHODS)
    if RandomForestRegressor is not None:
        methods.append("random_forest")
    if GradientBoostingRegressor is not None:
        methods.append("gradient_boosting")
    return tuple(methods)


def _validate_horizon(horizon):
    if horizon < 1:
        raise ValueError("horizon must be at least 1.")


def _normalize_methods(methods):
    if methods is None:
        methods = get_candidate_methods()
    elif isinstance(methods, str):
        methods = (methods,)

    methods = tuple(methods)
    if not methods:
        raise ValueError("methods must include at least one forecast method.")

    valid_methods = set(BASELINE_METHODS).union(ML_METHODS)
    invalid_methods = sorted(set(methods).difference(valid_methods))
    if invalid_methods:
        valid_method_text = ", ".join(sorted(valid_methods))
        raise ValueError(
            f"Unsupported forecast methods: {invalid_methods}. "
            f"Valid methods are: {valid_method_text}."
        )

    unavailable_methods = sorted(set(methods).difference(get_candidate_methods()))
    if unavailable_methods:
        raise ImportError(
            "scikit-learn is required for ML forecast candidates: "
            f"{unavailable_methods}."
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


def _prepare_market_factors(market_factors):
    if market_factors is None or market_factors.empty:
        return pd.DataFrame()
    if "date" not in market_factors.columns:
        return pd.DataFrame()

    available_columns = [
        column for column in MARKET_FACTOR_COLUMNS if column in market_factors.columns
    ]
    if not available_columns:
        return pd.DataFrame()

    factors = market_factors.copy()
    factors["date"] = pd.to_datetime(factors["date"], errors="coerce")
    factors = factors.dropna(subset=["date"])
    factors["week_start"] = factors["date"].dt.to_period("W-FRI").dt.start_time
    for column in available_columns:
        factors[column] = pd.to_numeric(factors[column], errors="coerce")

    return (
        factors.groupby("week_start")[available_columns]
        .mean()
        .sort_index()
    )


def _align_market_factors(index, market_factors):
    target_index = pd.DatetimeIndex(index, name="week_start")
    aligned = pd.DataFrame(index=target_index)
    prepared = _prepare_market_factors(market_factors)
    if prepared.empty:
        return aligned

    combined_index = prepared.index.union(target_index).sort_values()
    prepared = prepared.reindex(combined_index).ffill().bfill()
    return prepared.reindex(target_index)


def _calendar_features(index):
    if isinstance(index, pd.DatetimeIndex):
        return pd.DataFrame(
            {
                "week_of_year": index.isocalendar().week.astype(int).to_numpy(),
                "month": index.month,
            },
            index=index,
        )

    positions = np.arange(len(index))
    return pd.DataFrame(
        {
            "week_of_year": (positions % 52) + 1,
            "month": (positions % 12) + 1,
        },
        index=index,
    )


def _build_ml_feature_frame(series, market_factors=None):
    clean = _prepare_series(series)
    features = pd.DataFrame({"quantity_kg": clean}, index=clean.index)
    features["lag_1"] = features["quantity_kg"].shift(1)
    features["lag_2"] = features["quantity_kg"].shift(2)
    features["lag_4"] = features["quantity_kg"].shift(4)
    features["rolling_mean_4"] = (
        features["quantity_kg"].shift(1).rolling(4, min_periods=1).mean()
    )
    features["rolling_mean_8"] = (
        features["quantity_kg"].shift(1).rolling(8, min_periods=1).mean()
    )

    calendar = _calendar_features(features.index)
    features = features.join(calendar)

    if isinstance(features.index, pd.DatetimeIndex):
        market = _align_market_factors(features.index, market_factors)
        features = features.join(market)

    feature_columns = [
        column
        for column in [*ML_BASE_FEATURES, *MARKET_FACTOR_COLUMNS]
        if column in features.columns
    ]
    return features, feature_columns


def _make_ml_model(method):
    if method == "random_forest":
        if RandomForestRegressor is None:
            raise ImportError("scikit-learn is required for random_forest.")
        return RandomForestRegressor(
            n_estimators=100,
            random_state=42,
            min_samples_leaf=2,
        )
    if method == "gradient_boosting":
        if GradientBoostingRegressor is None:
            raise ImportError("scikit-learn is required for gradient_boosting.")
        return GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=2,
            random_state=42,
        )
    raise ValueError(f"Unsupported ML method: {method}.")


def _build_ml_prediction_row(history, forecast_index_value, feature_columns, market_factors):
    history = _prepare_series(history)
    row = {}
    row["lag_1"] = history.iloc[-1] if len(history) >= 1 else np.nan
    row["lag_2"] = history.iloc[-2] if len(history) >= 2 else np.nan
    row["lag_4"] = history.iloc[-4] if len(history) >= 4 else np.nan
    row["rolling_mean_4"] = history.tail(4).mean()
    row["rolling_mean_8"] = history.tail(8).mean()

    if isinstance(forecast_index_value, pd.Timestamp):
        row["week_of_year"] = int(forecast_index_value.isocalendar().week)
        row["month"] = forecast_index_value.month
        market = _align_market_factors(
            pd.DatetimeIndex([forecast_index_value]),
            market_factors,
        )
        for column in MARKET_FACTOR_COLUMNS:
            if column in market.columns:
                row[column] = market.iloc[0][column]
    else:
        row["week_of_year"] = ((len(history) + 1) % 52) + 1
        row["month"] = ((len(history) + 1) % 12) + 1

    return pd.DataFrame([{column: row.get(column, np.nan) for column in feature_columns}])


def _run_ml_forecast(series, forecast_index, method, market_factors=None):
    clean = _prepare_series(series)
    features, feature_columns = _build_ml_feature_frame(clean, market_factors)
    training = features.dropna(subset=[*feature_columns, "quantity_kg"])
    if len(training) < 8:
        raise ValueError(
            f"At least 8 complete feature rows are required for {method}."
        )

    model = _make_ml_model(method)
    x_train = training[feature_columns]
    y_train = training["quantity_kg"]
    model.fit(x_train, y_train)

    fallback_values = x_train.median(numeric_only=True).fillna(0)
    history = clean.copy()
    predictions = []
    for index_value in forecast_index:
        row = _build_ml_prediction_row(
            history,
            index_value,
            feature_columns,
            market_factors,
        )
        row = row.fillna(fallback_values).fillna(0)
        prediction = max(float(model.predict(row[feature_columns])[0]), 0)
        predictions.append(prediction)
        history.loc[index_value] = prediction
        history = history.sort_index()

    return pd.Series(predictions, index=forecast_index, name="forecast_quantity_kg")


def _run_method(series, method, horizon, window=4, market_factors=None):
    if method == "naive":
        return naive_forecast(series, horizon=horizon)
    if method == "moving_average":
        return moving_average_forecast(series, window=window, horizon=horizon)
    if method == "exponential_smoothing":
        return exponential_smoothing_forecast(series, horizon=horizon)
    if method in ML_METHODS:
        clean = _prepare_series(series)
        return _run_ml_forecast(
            clean,
            _future_index(clean, horizon),
            method,
            market_factors=market_factors,
        )
    valid_methods = ", ".join((*BASELINE_METHODS, *ML_METHODS))
    raise ValueError(f"method must be one of: {valid_methods}.")


def backtest_forecast(series, method="moving_average", window=4, market_factors=None):
    clean = _prepare_series(series)
    if len(clean) < 3:
        raise ValueError("At least 3 weekly observations are required for backtesting.")

    test_size = min(8, max(1, len(clean) // 4))
    train = clean.iloc[:-test_size]
    actual = clean.iloc[-test_size:]

    if train.empty:
        raise ValueError("Not enough history to create a train/test split.")

    if method in ML_METHODS:
        forecast = _run_ml_forecast(
            train,
            actual.index,
            method,
            market_factors=market_factors,
        )
    else:
        forecast = _run_method(
            train,
            method=method,
            horizon=test_size,
            window=window,
            market_factors=market_factors,
        )
        forecast.index = actual.index

    return {
        "method": method,
        "test_size": test_size,
        "actual": actual,
        "forecast": forecast,
        "mae": calculate_mae(actual, forecast),
        "wape": calculate_wape(actual, forecast),
    }


def get_backtest_predictions(series, method="moving_average", window=4, market_factors=None):
    backtest = backtest_forecast(
        series,
        method=method,
        window=window,
        market_factors=market_factors,
    )

    return pd.DataFrame(
        {
            "week_start": backtest["actual"].index,
            "actual_demand": backtest["actual"].to_numpy(),
            "forecast_demand": backtest["forecast"].to_numpy(),
            "method": backtest["method"],
        }
    )


def _load_market_factors_if_available():
    if not MARKET_FACTORS_PATH.exists():
        return None
    return pd.read_csv(MARKET_FACTORS_PATH)


def _rating_from_wape(wape):
    if pd.isna(wape):
        return "unrated"
    if wape < 0.20:
        return "strong"
    if wape < 0.35:
        return "acceptable"
    if wape < 0.60:
        return "weak"
    return "poor"


def _select_best_methods(metrics_df, methods):
    metrics = metrics_df.copy()
    method_order = {method: index for index, method in enumerate(methods)}
    metrics["_method_order"] = metrics["method"].map(method_order).fillna(999)
    metrics["_method_family_order"] = metrics["method"].apply(
        lambda method: 0 if method in BASELINE_METHODS else 1
    )
    eligible = metrics.dropna(subset=["wape"]).sort_values(
        [
            "product_id",
            "wape",
            "mae",
            "_method_family_order",
            "_method_order",
        ]
    )
    selected_indexes = (
        eligible.groupby("product_id", as_index=False)
        .head(1)
        .index
    )
    metrics["is_selected_method"] = metrics.index.isin(selected_indexes)
    return metrics.drop(columns=["_method_order", "_method_family_order"])


def forecast_all_products(orders, products, horizon=8, methods=None, market_factors=None):
    _validate_horizon(horizon)
    methods = _normalize_methods(methods)
    if market_factors is None:
        market_factors = _load_market_factors_if_available()

    required_product_columns = {"product_id", "product_name", "product_group"}
    missing_columns = required_product_columns.difference(products.columns)
    if missing_columns:
        raise ValueError(f"products is missing required columns: {sorted(missing_columns)}")

    metric_rows = []
    weekly_by_product = {}
    product_info_by_id = {}

    for product in products.sort_values("product_id").itertuples(index=False):
        weekly = aggregate_weekly_demand(orders, product_id=product.product_id)
        product_info = {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "product_group": product.product_group,
        }
        weekly_by_product[product.product_id] = weekly
        product_info_by_id[product.product_id] = product_info

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

        for method in methods:
            try:
                backtest = backtest_forecast(
                    weekly,
                    method=method,
                    market_factors=market_factors,
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
            except (ImportError, ValueError):
                metric_rows.append(
                    {
                        **product_info,
                        "method": method,
                        "mae": np.nan,
                        "wape": np.nan,
                        "test_weeks": min(8, max(1, len(weekly) // 4)),
                        "history_weeks": len(weekly),
                        "forecast_horizon_weeks": horizon,
                    }
                )

    metrics_df = pd.DataFrame(metric_rows)
    metrics_df = _select_best_methods(metrics_df, methods)
    metrics_df["MAE"] = metrics_df["mae"]
    metrics_df["WAPE"] = metrics_df["wape"]
    metrics_df = metrics_df[METRIC_COLUMNS]

    selected_metrics = metrics_df[metrics_df["is_selected_method"]].copy()
    selected_method_rows = []
    forecast_rows = []
    for selected in selected_metrics.sort_values("product_id").itertuples(index=False):
        product_info = product_info_by_id[selected.product_id]
        weekly = weekly_by_product[selected.product_id]
        if weekly.empty:
            continue

        forecast = _run_method(
            weekly,
            method=selected.method,
            horizon=horizon,
            market_factors=market_factors,
        )
        selected_method_rows.append(
            {
                "product_id": selected.product_id,
                "product_name": selected.product_name,
                "selected_method": selected.method,
                "selected_method_mae": selected.mae,
                "selected_method_wape": selected.wape,
                "rating": _rating_from_wape(selected.wape),
            }
        )

        for week_start, quantity_kg in forecast.items():
            forecast_rows.append(
                {
                    **product_info,
                    "forecast_period": week_start,
                    "week_start": week_start,
                    "record_type": "forecast",
                    "actual_quantity_kg": np.nan,
                    "forecast_quantity_kg": quantity_kg,
                    "method": selected.method,
                    "selected_method": selected.method,
                    "selected_method_wape": selected.wape,
                }
            )

    forecast_df = pd.DataFrame(forecast_rows, columns=FORECAST_COLUMNS)
    selected_methods_df = pd.DataFrame(
        selected_method_rows,
        columns=SELECTED_METHOD_COLUMNS,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    forecast_df.to_csv(OUTPUT_DIR / "product_forecasts.csv", index=False)
    metrics_df.to_csv(OUTPUT_DIR / "forecast_metrics.csv", index=False)
    selected_methods_df.to_csv(
        OUTPUT_DIR / "selected_forecast_methods.csv",
        index=False,
    )

    return forecast_df, metrics_df
