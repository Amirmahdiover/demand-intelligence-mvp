from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_loader import load_market_factors, load_orders, load_products
from src.forecast import (
    aggregate_weekly_demand,
    forecast_all_products,
    get_backtest_predictions,
    get_candidate_methods,
)


CHART_DIR = ROOT_DIR / "outputs" / "charts"
METHOD_LABELS = {
    "naive": "Naive",
    "moving_average": "Moving average",
    "exponential_smoothing": "Exponential smoothing",
    "random_forest": "Random forest",
    "gradient_boosting": "Gradient boosting",
}


def plot_example_product(forecast_df, product_id, actual_weekly):
    product_rows = forecast_df[forecast_df["product_id"] == product_id].copy()
    product_rows["week_start"] = pd.to_datetime(product_rows["week_start"])

    forecast = product_rows[product_rows["record_type"] == "forecast"]
    product_name = product_rows["product_name"].iloc[0]
    actual = actual_weekly.tail(26).reset_index()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(
        actual["week_start"],
        actual["quantity_kg"] / 1000,
        marker="o",
        label="Actual demand",
    )

    for method in sorted(forecast["method"].dropna().unique()):
        method_forecast = forecast[forecast["method"] == method]
        if method_forecast.empty:
            continue

        ax.plot(
            method_forecast["week_start"],
            method_forecast["forecast_quantity_kg"] / 1000,
            marker="o",
            linestyle="--",
            label=f"{METHOD_LABELS.get(method, method)} forecast",
        )

    ax.set_title(f"Selected Forecast Method - {product_name}")
    ax.set_xlabel("Week")
    ax.set_ylabel("Demand (tons)")
    ax.grid(alpha=0.25)
    ax.legend()

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CHART_DIR / "baseline_forecast_model_comparison.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_backtest_product(backtest_df, product_name, method):
    backtest_df = backtest_df.copy()
    backtest_df["week_start"] = pd.to_datetime(backtest_df["week_start"])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(
        backtest_df["week_start"],
        backtest_df["actual_demand"] / 1000,
        marker="o",
        label="Actual demand",
    )
    ax.plot(
        backtest_df["week_start"],
        backtest_df["forecast_demand"] / 1000,
        marker="o",
        linestyle="--",
        label=f"Backtest {METHOD_LABELS.get(method, method)} forecast",
    )
    ax.set_title(f"Backtest: Actual vs Selected Forecast - {product_name}")
    ax.set_xlabel("Week")
    ax.set_ylabel("Demand (tons)")
    ax.grid(alpha=0.25)
    ax.legend()

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CHART_DIR / "backtest_actual_vs_forecast.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def format_metrics(metrics_df):
    metrics_view = metrics_df.copy()
    metrics_view["mae"] = metrics_view["mae"].round(2)
    metrics_view["wape"] = metrics_view["wape"].round(4)
    return metrics_view


def main():
    orders = load_orders()
    products = load_products()
    market_factors = load_market_factors()
    candidate_methods = get_candidate_methods()

    weekly_total = aggregate_weekly_demand(orders)
    forecast_df, metrics_df = forecast_all_products(
        orders,
        products,
        horizon=8,
        methods=candidate_methods,
        market_factors=market_factors,
    )

    actual_totals = pd.Series(
        {
            product_id: aggregate_weekly_demand(orders, product_id=product_id).sum()
            for product_id in products["product_id"]
        }
    ).sort_values(ascending=False)
    selected_methods = (
        metrics_df[metrics_df["is_selected_method"]]
        .set_index("product_id")
        .sort_index()
    )
    example_product_id = actual_totals.index[0]
    example_product = products[products["product_id"] == example_product_id].iloc[0]
    example_weekly = aggregate_weekly_demand(orders, product_id=example_product_id)
    example_method = selected_methods.loc[example_product_id, "method"]
    backtest_df = get_backtest_predictions(
        example_weekly,
        method=example_method,
        window=4,
        market_factors=market_factors,
    )

    chart_path = plot_example_product(
        forecast_df,
        example_product_id,
        example_weekly,
    )
    backtest_chart_path = plot_backtest_product(
        backtest_df,
        example_product["product_name"],
        example_method,
    )

    metrics_view = format_metrics(metrics_df)
    method_order = {method: index for index, method in enumerate(candidate_methods)}
    metrics_view["method_order"] = metrics_view["method"].map(method_order)
    metrics_by_product = metrics_view.sort_values(["product_id", "method_order"])
    model_comparison = metrics_view.sort_values(
        ["product_id", "wape", "mae", "method_order"]
    )
    best_by_product = (
        model_comparison.dropna(subset=["wape"])
        .groupby("product_id", as_index=False)
        .first()
    )

    print("Forecast model comparison complete.")
    print(f"Weekly observations in total demand series: {len(weekly_total)}")
    print("Metrics by product and method:")
    print(
        metrics_by_product[
            ["product_id", "product_name", "method", "mae", "wape"]
        ].to_string(index=False)
    )
    print("")
    print("Model comparison by product (lower MAE/WAPE is better):")
    print(
        model_comparison[
            ["product_id", "product_name", "method", "mae", "wape"]
        ].to_string(index=False)
    )
    print("")
    print("Best method per product by WAPE:")
    print(
        best_by_product[
            ["product_id", "product_name", "method", "mae", "wape"]
        ].to_string(index=False)
    )
    print(f"Forecast files saved to: {ROOT_DIR / 'outputs' / 'forecast'}")
    print(f"Model comparison chart saved to: {chart_path}")
    print(f"Backtest chart saved to: {backtest_chart_path}")
    print("")
    print("Limitations:")
    print("- This is a baseline forecast, not a production-grade forecasting system.")
    print("- It uses synthetic historical orders, so accuracy does not prove real factory accuracy.")
    print("- It does not yet use sales notes, customer commitments, inventory constraints, or market scenarios.")
    print("- ML candidates are lightweight scikit-learn models and are only selected when WAPE improves.")


if __name__ == "__main__":
    main()
