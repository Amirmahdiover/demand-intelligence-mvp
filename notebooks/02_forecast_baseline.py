from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_loader import load_orders, load_products
from src.forecast import (
    aggregate_weekly_demand,
    forecast_all_products,
    get_backtest_predictions,
)


CHART_DIR = ROOT_DIR / "outputs" / "charts"


def plot_example_product(forecast_df, product_id):
    product_rows = forecast_df[forecast_df["product_id"] == product_id].copy()
    product_rows["week_start"] = pd.to_datetime(product_rows["week_start"])

    actual = product_rows[product_rows["record_type"] == "actual"].tail(26)
    forecast = product_rows[product_rows["record_type"] == "forecast"]
    product_name = product_rows["product_name"].iloc[0]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(
        actual["week_start"],
        actual["actual_quantity_kg"] / 1000,
        marker="o",
        label="Actual demand",
    )
    ax.plot(
        forecast["week_start"],
        forecast["forecast_quantity_kg"] / 1000,
        marker="o",
        linestyle="--",
        label="8-week moving average forecast",
    )
    ax.set_title(f"Historical Demand and Next 8-Week Forecast - {product_name}")
    ax.set_xlabel("Week")
    ax.set_ylabel("Demand (tons)")
    ax.grid(alpha=0.25)
    ax.legend()

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CHART_DIR / "baseline_forecast_actual_vs_forecast.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_backtest_product(backtest_df, product_name):
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
        label="Backtest moving average forecast",
    )
    ax.set_title(f"Backtest: Actual vs Forecast Demand - {product_name}")
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


def main():
    orders = load_orders()
    products = load_products()

    weekly_total = aggregate_weekly_demand(orders)
    forecast_df, metrics_df = forecast_all_products(orders, products, horizon=8)

    actual_totals = (
        forecast_df[forecast_df["record_type"] == "actual"]
        .groupby("product_id")["actual_quantity_kg"]
        .sum()
        .sort_values(ascending=False)
    )
    example_product_id = actual_totals.index[0]
    example_product = products[products["product_id"] == example_product_id].iloc[0]
    example_weekly = aggregate_weekly_demand(orders, product_id=example_product_id)
    backtest_df = get_backtest_predictions(example_weekly, method="moving_average", window=4)

    chart_path = plot_example_product(forecast_df, example_product_id)
    backtest_chart_path = plot_backtest_product(
        backtest_df,
        example_product["product_name"],
    )

    print("Baseline forecast complete.")
    print(f"Weekly observations in total demand series: {len(weekly_total)}")
    print("Metrics by product:")
    print(metrics_df[["product_id", "product_name", "mae", "wape"]].to_string(index=False))
    print(f"Forecast files saved to: {ROOT_DIR / 'outputs' / 'forecast'}")
    print(f"Example chart saved to: {chart_path}")
    print(f"Backtest chart saved to: {backtest_chart_path}")
    print("")
    print("Limitations:")
    print("- This is a baseline forecast, not a production-grade forecasting system.")
    print("- It uses synthetic historical orders, so accuracy does not prove real factory accuracy.")
    print("- It does not yet use sales notes, customer commitments, inventory constraints, or market scenarios.")
    print("- Moving average forecasts are easy to explain but can lag when demand changes quickly.")


if __name__ == "__main__":
    main()
