from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_loader import load_all_data
from src.utils import ensure_datetime


CHART_DIR = ROOT_DIR / "outputs" / "charts"
INSIGHTS_PATH = ROOT_DIR / "docs" / "eda_insights.md"
DEMAND_STATUSES = {"completed", "delivered", "pending"}


def prepare_data():
    data = load_all_data()

    orders = ensure_datetime(data["orders"], ["order_date", "delivery_date"])
    sales_notes = ensure_datetime(data["sales_notes"], ["note_date"])
    market_factors = ensure_datetime(data["market_factors"], ["date"])
    customers = data["customers"].copy()
    products = data["products"].copy()
    inventory = data["inventory"].copy()

    orders = orders.merge(customers, on="customer_id", how="left")
    orders = orders.merge(products, on="product_id", how="left")

    if orders[["customer_name", "product_name"]].isna().any().any():
        raise ValueError("Some orders could not be matched to customers or products.")

    demand_orders = orders[orders["status"].isin(DEMAND_STATUSES)].copy()
    demand_orders["month"] = demand_orders["order_date"].dt.to_period("M").dt.to_timestamp()
    demand_orders["week_start"] = demand_orders["order_date"].dt.to_period("W-SAT").dt.start_time
    demand_orders["export_group"] = np.where(
        demand_orders["export_related"].astype(str).str.lower().eq("true"),
        "Export-related",
        "Non-export",
    )

    return {
        "orders": orders,
        "demand_orders": demand_orders,
        "customers": customers,
        "products": products,
        "sales_notes": sales_notes,
        "market_factors": market_factors,
        "inventory": inventory,
    }


def build_analyses(demand_orders, market_factors):
    monthly_total = demand_orders.groupby("month")["quantity_kg"].sum().sort_index()

    demand_by_product = (
        demand_orders.groupby(["product_id", "product_name"], as_index=False)["quantity_kg"]
        .sum()
        .rename(columns={"quantity_kg": "total_quantity_kg"})
        .sort_values("total_quantity_kg", ascending=False)
    )

    demand_by_customer = (
        demand_orders.groupby(["customer_id", "customer_name"], as_index=False)["quantity_kg"]
        .sum()
        .rename(columns={"quantity_kg": "total_quantity_kg"})
        .sort_values("total_quantity_kg", ascending=False)
    )
    top_customers = demand_by_customer.head(10)

    monthly_product = demand_orders.pivot_table(
        index="month",
        columns="product_name",
        values="quantity_kg",
        aggfunc="sum",
        fill_value=0,
    )
    volatility = pd.DataFrame(
        {
            "product_name": monthly_product.columns,
            "avg_monthly_quantity_kg": monthly_product.mean().to_numpy(),
            "std_monthly_quantity_kg": monthly_product.std().to_numpy(),
        }
    )
    volatility["coefficient_of_variation"] = (
        volatility["std_monthly_quantity_kg"] / volatility["avg_monthly_quantity_kg"]
    ).replace([np.inf, -np.inf], np.nan)
    volatility = volatility.sort_values("coefficient_of_variation", ascending=False)

    weekly_demand = (
        demand_orders.groupby("week_start", as_index=False)["quantity_kg"]
        .sum()
        .rename(columns={"week_start": "date"})
    )
    weekly_market = market_factors.merge(weekly_demand, on="date", how="left")
    weekly_market["quantity_kg"] = weekly_market["quantity_kg"].fillna(0)

    export_monthly = demand_orders.pivot_table(
        index="month",
        columns="export_group",
        values="quantity_kg",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()

    return {
        "monthly_total": monthly_total,
        "demand_by_product": demand_by_product,
        "demand_by_customer": demand_by_customer,
        "top_customers": top_customers,
        "volatility": volatility,
        "weekly_market": weekly_market,
        "export_monthly": export_monthly,
    }


def save_chart(fig, filename):
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHART_DIR / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)


def create_charts(analyses):
    monthly_total = analyses["monthly_total"]
    demand_by_product = analyses["demand_by_product"]
    top_customers = analyses["top_customers"]
    volatility = analyses["volatility"]
    weekly_market = analyses["weekly_market"]
    export_monthly = analyses["export_monthly"]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(monthly_total.index, monthly_total.values / 1000, marker="o")
    ax.set_title("Monthly Total Demand")
    ax.set_xlabel("Month")
    ax.set_ylabel("Demand (tons)")
    ax.grid(alpha=0.25)
    save_chart(fig, "monthly_total_demand.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    product_plot = demand_by_product.sort_values("total_quantity_kg")
    ax.barh(product_plot["product_name"], product_plot["total_quantity_kg"] / 1000)
    ax.set_title("Demand by Product")
    ax.set_xlabel("Total demand (tons)")
    save_chart(fig, "demand_by_product.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    customer_plot = top_customers.sort_values("total_quantity_kg")
    ax.barh(customer_plot["customer_name"], customer_plot["total_quantity_kg"] / 1000)
    ax.set_title("Top Customers by Total Quantity")
    ax.set_xlabel("Total demand (tons)")
    save_chart(fig, "top_customers_by_quantity.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    volatility_plot = volatility.sort_values("coefficient_of_variation")
    ax.barh(volatility_plot["product_name"], volatility_plot["coefficient_of_variation"])
    ax.set_title("Demand Volatility by Product")
    ax.set_xlabel("Coefficient of variation")
    save_chart(fig, "demand_volatility_by_product.png")

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(weekly_market["date"], weekly_market["quantity_kg"] / 1000, color="tab:blue")
    ax1.set_xlabel("Week")
    ax1.set_ylabel("Demand (tons)", color="tab:blue")
    ax2 = ax1.twinx()
    ax2.plot(weekly_market["date"], weekly_market["pet_price_index"], color="tab:red")
    ax2.set_ylabel("PET price index", color="tab:red")
    ax1.set_title("PET Price Index vs Weekly Demand")
    save_chart(fig, "pet_price_index_vs_demand.png")

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(weekly_market["date"], weekly_market["quantity_kg"] / 1000, color="tab:blue")
    ax1.set_xlabel("Week")
    ax1.set_ylabel("Demand (tons)", color="tab:blue")
    ax2 = ax1.twinx()
    ax2.plot(weekly_market["date"], weekly_market["usd_rate"], color="tab:green")
    ax2.set_ylabel("USD rate", color="tab:green")
    ax1.set_title("USD Rate vs Weekly Demand")
    save_chart(fig, "usd_rate_vs_demand.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    for column in export_monthly.columns:
        ax.plot(export_monthly.index, export_monthly[column] / 1000, marker="o", label=column)
    ax.set_title("Export-related vs Non-export Demand")
    ax.set_xlabel("Month")
    ax.set_ylabel("Demand (tons)")
    ax.legend()
    ax.grid(alpha=0.25)
    save_chart(fig, "export_vs_non_export_demand.png")


def correlation_label(value):
    if pd.isna(value):
        return "not enough data to calculate a clear relationship"
    direction = "positive" if value >= 0 else "negative"
    strength = "weak"
    if abs(value) >= 0.6:
        strength = "strong"
    elif abs(value) >= 0.3:
        strength = "moderate"
    return f"a {strength} {direction} relationship (correlation {value:.2f})"


def write_insights(analyses):
    monthly_total = analyses["monthly_total"]
    demand_by_product = analyses["demand_by_product"]
    demand_by_customer = analyses["demand_by_customer"]
    top_customers = analyses["top_customers"]
    volatility = analyses["volatility"]
    weekly_market = analyses["weekly_market"]
    export_monthly = analyses["export_monthly"]

    total_demand = monthly_total.sum()
    top_product = demand_by_product.iloc[0]
    top_customer = demand_by_customer.iloc[0]
    peak_month = monthly_total.idxmax().strftime("%Y-%m")
    low_month = monthly_total.idxmin().strftime("%Y-%m")
    top_5_share = top_customers.head(5)["total_quantity_kg"].sum() / total_demand
    volatile_product = volatility.iloc[0]

    pet_correlation = weekly_market["quantity_kg"].corr(weekly_market["pet_price_index"])
    usd_correlation = weekly_market["quantity_kg"].corr(weekly_market["usd_rate"])

    export_totals = export_monthly.sum()
    export_related_total = export_totals.get("Export-related", 0)
    export_share = export_related_total / total_demand

    lines = [
        "# EDA Insights",
        "",
        "Generated by `notebooks/01_eda.py` using non-cancelled orders only.",
        "",
        "## Business Insights",
        "",
        f"1. Total demand peaks in {peak_month} and is lowest in {low_month}. Demand planning should review PET Chips coverage before the peak month instead of reacting after orders arrive.",
        f"2. {top_product['product_name']} is the highest-demand product with {top_product['total_quantity_kg'] / 1000:,.1f} tons. This product should receive the first weekly forecast review.",
        f"3. The top customer is {top_customer['customer_name']} with {top_customer['total_quantity_kg'] / 1000:,.1f} tons. Losing or delaying this account would create a visible demand planning gap.",
        f"4. The top five customers represent {top_5_share:.1%} of total demand. Account-level sales notes from these customers are especially important early demand signals.",
        f"5. {volatile_product['product_name']} has the highest demand volatility with a coefficient of variation of {volatile_product['coefficient_of_variation']:.2f}. This product needs closer safety-stock and production review.",
        f"6. PET price index and weekly demand show {correlation_label(pet_correlation)}. Price changes should be monitored as a demand-timing signal, not treated as the only demand driver.",
        f"7. USD rate and weekly demand show {correlation_label(usd_correlation)}. Export-sensitive customers may need separate review when exchange-rate pressure changes.",
        f"8. Export-related customers represent {export_share:.1%} of total demand. Splitting export and non-export demand helps planners avoid hiding export risk inside one total number.",
        "",
        "## Practical Planning Notes",
        "",
        "- The EDA is directional because the dataset is synthetic.",
        "- The next useful step is a simple weekly baseline forecast by product, then a comparison with sales-note signals.",
    ]

    INSIGHTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    prepared = prepare_data()
    analyses = build_analyses(prepared["demand_orders"], prepared["market_factors"])
    create_charts(analyses)
    write_insights(analyses)

    print("EDA complete.")
    print(f"Charts saved to: {CHART_DIR}")
    print(f"Insights saved to: {INSIGHTS_PATH}")


if __name__ == "__main__":
    main()
