from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
FORECAST_PATH = ROOT_DIR / "outputs" / "forecast" / "product_forecasts.csv"
SIGNALS_PATH = ROOT_DIR / "outputs" / "signals" / "extracted_sales_signals.csv"
PRODUCTS_PATH = ROOT_DIR / "data" / "products.csv"
INVENTORY_PATH = ROOT_DIR / "data" / "inventory.csv"
OUTPUT_DIR = ROOT_DIR / "outputs" / "planning"
OUTPUT_PATH = OUTPUT_DIR / "material_risk.csv"

DEFAULT_BASELINE_METHOD = "moving_average"

OUTPUT_COLUMNS = [
    "product_id",
    "product_name",
    "product_group",
    "baseline_method",
    "baseline_forecast_kg",
    "sales_signal_adjustment_kg",
    "adjusted_forecast_kg",
    "kg_pet_per_kg_product",
    "required_pet_kg",
    "material_name",
    "current_inventory_kg",
    "safety_stock_kg",
    "available_after_safety_kg",
    "shortage_or_surplus_kg",
    "shortage_kg",
    "coverage_ratio",
    "shortage_ratio",
    "risk_level",
    "priority_rank",
]


def _validate_columns(df, required_columns, table_name):
    missing_columns = set(required_columns).difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: {sorted(missing_columns)}"
        )


def load_supply_planning_inputs(
    forecast_path=FORECAST_PATH,
    signals_path=SIGNALS_PATH,
    products_path=PRODUCTS_PATH,
    inventory_path=INVENTORY_PATH,
):
    forecast_df = pd.read_csv(forecast_path)
    signals_df = pd.read_csv(signals_path)
    products_df = pd.read_csv(products_path)
    inventory_df = pd.read_csv(inventory_path)

    _validate_columns(
        forecast_df,
        {
            "product_id",
            "record_type",
            "forecast_quantity_kg",
            "method",
        },
        "product_forecasts",
    )
    _validate_columns(
        signals_df,
        {
            "product_id",
            "expected_quantity_kg",
            "intent_probability",
        },
        "extracted_sales_signals",
    )
    _validate_columns(
        products_df,
        {
            "product_id",
            "product_name",
            "product_group",
            "kg_pet_per_kg_product",
        },
        "products",
    )
    _validate_columns(
        inventory_df,
        {
            "material_name",
            "current_inventory_kg",
            "safety_stock_kg",
        },
        "inventory",
    )

    return forecast_df, signals_df, products_df, inventory_df


def aggregate_baseline_forecast(forecast_df, baseline_method=DEFAULT_BASELINE_METHOD):
    forecast_rows = forecast_df[
        (forecast_df["record_type"] == "forecast")
        & (forecast_df["method"] == baseline_method)
    ].copy()

    if forecast_rows.empty:
        raise ValueError(
            f"No forecast rows found for baseline method '{baseline_method}'."
        )

    forecast_rows["forecast_quantity_kg"] = pd.to_numeric(
        forecast_rows["forecast_quantity_kg"],
        errors="coerce",
    ).fillna(0)

    baseline = (
        forecast_rows.groupby("product_id", as_index=False)["forecast_quantity_kg"]
        .sum()
        .rename(columns={"forecast_quantity_kg": "baseline_forecast_kg"})
    )
    baseline["baseline_method"] = baseline_method
    return baseline


def aggregate_sales_signal_adjustments(signals_df):
    signals = signals_df.copy()
    signals = signals[signals["product_id"].notna()]
    signals["expected_quantity_kg"] = pd.to_numeric(
        signals["expected_quantity_kg"],
        errors="coerce",
    )
    signals["intent_probability"] = pd.to_numeric(
        signals["intent_probability"],
        errors="coerce",
    ).fillna(0)
    signals["sales_signal_adjustment_kg"] = (
        signals["expected_quantity_kg"] * signals["intent_probability"]
    )

    adjustments = (
        signals.groupby("product_id", as_index=False)["sales_signal_adjustment_kg"]
        .sum(min_count=1)
        .fillna({"sales_signal_adjustment_kg": 0})
    )
    return adjustments


def safe_ratio(numerator, denominator):
    if pd.isna(denominator) or denominator <= 0:
        return 0
    return numerator / denominator


def calculate_risk_level(shortage_kg, shortage_ratio):
    if pd.isna(shortage_kg) or shortage_kg == 0:
        return "ok"
    if shortage_ratio >= 0.50:
        return "critical_shortage"
    if shortage_ratio >= 0.25:
        return "high_shortage"
    if shortage_ratio >= 0.10:
        return "medium_shortage"
    return "low_shortage"


def build_material_risk_plan(
    forecast_df,
    signals_df,
    products_df,
    inventory_df,
    baseline_method=DEFAULT_BASELINE_METHOD,
):
    baseline = aggregate_baseline_forecast(forecast_df, baseline_method=baseline_method)
    adjustments = aggregate_sales_signal_adjustments(signals_df)

    inventory = inventory_df.iloc[0]
    material_name = inventory["material_name"]
    current_inventory_kg = float(inventory["current_inventory_kg"])
    safety_stock_kg = float(inventory["safety_stock_kg"])
    available_after_safety_kg = current_inventory_kg - safety_stock_kg

    planning = products_df.merge(baseline, on="product_id", how="left")
    planning = planning.merge(adjustments, on="product_id", how="left")
    planning["baseline_method"] = planning["baseline_method"].fillna(baseline_method)
    planning["baseline_forecast_kg"] = planning["baseline_forecast_kg"].fillna(0)
    planning["sales_signal_adjustment_kg"] = planning[
        "sales_signal_adjustment_kg"
    ].fillna(0)

    planning["adjusted_forecast_kg"] = (
        planning["baseline_forecast_kg"] + planning["sales_signal_adjustment_kg"]
    )
    planning["required_pet_kg"] = (
        planning["adjusted_forecast_kg"] * planning["kg_pet_per_kg_product"]
    )
    planning["material_name"] = material_name
    planning["current_inventory_kg"] = current_inventory_kg
    planning["safety_stock_kg"] = safety_stock_kg
    planning["available_after_safety_kg"] = available_after_safety_kg
    planning["shortage_or_surplus_kg"] = (
        planning["available_after_safety_kg"] - planning["required_pet_kg"]
    )
    planning["shortage_kg"] = planning["shortage_or_surplus_kg"].apply(
        lambda value: abs(value) if value < 0 else 0
    )
    planning["coverage_ratio"] = planning.apply(
        lambda row: safe_ratio(
            row["available_after_safety_kg"],
            row["required_pet_kg"],
        ),
        axis=1,
    )
    planning["shortage_ratio"] = planning.apply(
        lambda row: safe_ratio(row["shortage_kg"], row["required_pet_kg"]),
        axis=1,
    )
    planning["risk_level"] = planning.apply(
        lambda row: calculate_risk_level(
            row["shortage_kg"],
            row["shortage_ratio"],
        ),
        axis=1,
    )
    planning["priority_rank"] = (
        planning["shortage_kg"].rank(method="dense", ascending=False).astype(int)
    )

    quantity_columns = [
        "baseline_forecast_kg",
        "sales_signal_adjustment_kg",
        "adjusted_forecast_kg",
        "required_pet_kg",
        "current_inventory_kg",
        "safety_stock_kg",
        "available_after_safety_kg",
        "shortage_or_surplus_kg",
        "shortage_kg",
    ]
    ratio_columns = ["coverage_ratio", "shortage_ratio"]
    planning[quantity_columns] = planning[quantity_columns].round(2)
    planning[ratio_columns] = planning[ratio_columns].round(4)

    return planning[OUTPUT_COLUMNS]


def run_supply_planning(
    forecast_path=FORECAST_PATH,
    signals_path=SIGNALS_PATH,
    products_path=PRODUCTS_PATH,
    inventory_path=INVENTORY_PATH,
    output_path=OUTPUT_PATH,
    baseline_method=DEFAULT_BASELINE_METHOD,
):
    forecast_df, signals_df, products_df, inventory_df = load_supply_planning_inputs(
        forecast_path=forecast_path,
        signals_path=signals_path,
        products_path=products_path,
        inventory_path=inventory_path,
    )
    material_risk_df = build_material_risk_plan(
        forecast_df,
        signals_df,
        products_df,
        inventory_df,
        baseline_method=baseline_method,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    material_risk_df.to_csv(output_path, index=False)

    print("Supply planning complete.")
    print(f"Products processed: {len(material_risk_df)}")
    print(
        f"Total baseline forecast kg: "
        f"{material_risk_df['baseline_forecast_kg'].sum():,.2f}"
    )
    print(
        f"Total adjusted forecast kg: "
        f"{material_risk_df['adjusted_forecast_kg'].sum():,.2f}"
    )
    print(
        f"Total required PET kg: "
        f"{material_risk_df['required_pet_kg'].sum():,.2f}"
    )
    print(
        "Number of shortage risks: "
        f"{(material_risk_df['risk_level'] != 'ok').sum()}"
    )
    print(f"Output file: {output_path}")

    return material_risk_df


if __name__ == "__main__":
    run_supply_planning()
