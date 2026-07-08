from pathlib import Path

import pandas as pd
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent
ORDERS_PATH = ROOT_DIR / "data" / "orders.csv"
FORECAST_PATH = ROOT_DIR / "outputs" / "forecast" / "product_forecasts.csv"
FORECAST_METRICS_PATH = ROOT_DIR / "outputs" / "forecast" / "forecast_metrics.csv"
SIGNALS_PATH = ROOT_DIR / "outputs" / "signals" / "extracted_sales_signals.csv"
MATERIAL_RISK_PATH = ROOT_DIR / "outputs" / "planning" / "material_risk.csv"


@st.cache_data
def load_csv(path, modified_time):
    return pd.read_csv(path)


def load_dashboard_data():
    missing_files = [
        str(path)
        for path in [
            ORDERS_PATH,
            FORECAST_PATH,
            FORECAST_METRICS_PATH,
            SIGNALS_PATH,
            MATERIAL_RISK_PATH,
        ]
        if not path.exists()
    ]
    if missing_files:
        st.error("Missing required output files. Run the MVP pipeline first.")
        st.write(missing_files)
        st.stop()

    return {
        "orders": load_csv(ORDERS_PATH, ORDERS_PATH.stat().st_mtime),
        "forecast": load_csv(FORECAST_PATH, FORECAST_PATH.stat().st_mtime),
        "forecast_metrics": load_csv(
            FORECAST_METRICS_PATH,
            FORECAST_METRICS_PATH.stat().st_mtime,
        ),
        "signals": load_csv(SIGNALS_PATH, SIGNALS_PATH.stat().st_mtime),
        "material_risk": load_csv(
            MATERIAL_RISK_PATH,
            MATERIAL_RISK_PATH.stat().st_mtime,
        ),
    }


def filter_by_product(df, selected_product):
    if selected_product == "All products" or "product_name" not in df.columns:
        return df
    return df[df["product_name"] == selected_product]


def show_overview(orders_df, material_risk_df, signals_df):
    total_historical_demand = orders_df["quantity_kg"].sum()
    number_of_products = material_risk_df["product_id"].nunique()
    number_of_sales_signals = len(signals_df)
    number_of_risk_alerts = (material_risk_df["risk_level"] != "ok").sum()

    st.header("Overview")
    st.write(
        "High-level summary of historical demand, products, extracted sales "
        "signals, and current risk alerts."
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Historical demand kg", f"{total_historical_demand:,.0f}")
    col2.metric("Products", f"{number_of_products:,}")
    col3.metric("Sales signals", f"{number_of_sales_signals:,}")
    col4.metric("Risk alerts", f"{number_of_risk_alerts:,}")


def show_forecast(forecast_df, material_risk_df, selected_product):
    st.header("Forecast")
    st.write(
        "Baseline forecast is based only on historical demand. Adjusted forecast "
        "adds the weighted impact of extracted sales signals."
    )

    forecast_rows = forecast_df[forecast_df["record_type"] == "forecast"].copy()
    forecast_rows = filter_by_product(forecast_rows, selected_product)

    if "selected_method" in forecast_rows.columns:
        baseline_forecast = forecast_rows
        baseline_columns = [
            "product_id",
            "product_name",
            "week_start",
            "forecast_quantity_kg",
            "selected_method",
            "selected_method_wape",
        ]
    else:
        methods = sorted(forecast_rows["method"].dropna().unique())
        default_method_index = (
            methods.index("moving_average") if "moving_average" in methods else 0
        )
        selected_method = st.selectbox(
            "Baseline forecast method",
            methods,
            index=default_method_index,
        )
        baseline_forecast = forecast_rows[forecast_rows["method"] == selected_method]
        baseline_columns = [
            "product_id",
            "product_name",
            "week_start",
            "forecast_quantity_kg",
            "method",
        ]
    st.subheader("Baseline Forecast")
    st.dataframe(baseline_forecast[baseline_columns], use_container_width=True)

    adjusted_forecast = filter_by_product(material_risk_df, selected_product)
    adjusted_columns = [
        "product_id",
        "product_name",
        "baseline_forecast_kg",
        "sales_signal_adjustment_kg",
        "adjusted_forecast_kg",
    ]
    st.subheader("Adjusted Forecast")
    st.caption(
        "adjusted_forecast_kg = baseline_forecast_kg + "
        "sales_signal_adjustment_kg"
    )
    st.dataframe(adjusted_forecast[adjusted_columns], use_container_width=True)


def interpret_wape(wape):
    if wape < 0.20:
        return "Strong for MVP baseline"
    if wape < 0.35:
        return "Acceptable baseline"
    if wape < 0.60:
        return "Weak baseline"
    return "Poor baseline, reference only"


def show_forecast_evaluation(forecast_metrics_df, selected_product):
    st.header("Forecast Evaluation")
    st.write(
        "WAPE shows forecast error relative to actual demand. Lower is better. "
        "This currently evaluates the baseline forecast, not necessarily the "
        "adjusted forecast with sales signals."
    )

    metrics = filter_by_product(forecast_metrics_df, selected_product).copy()
    metrics["interpretation"] = metrics["wape"].apply(interpret_wape)

    summary_metrics = metrics
    if "is_selected_method" in metrics.columns:
        selected_mask = (
            metrics["is_selected_method"]
            .astype(str)
            .str.lower()
            .isin(["true", "1"])
        )
        if selected_mask.any():
            summary_metrics = metrics[selected_mask].copy()

    average_wape = summary_metrics["wape"].mean()
    best_row = summary_metrics.loc[summary_metrics["wape"].idxmin()]
    worst_row = summary_metrics.loc[summary_metrics["wape"].idxmax()]

    col1, col2, col3 = st.columns(3)
    col1.metric("Average WAPE", f"{average_wape:.3f}")
    col2.metric(
        "Best product by WAPE",
        best_row["product_name"],
        f"{best_row['wape']:.3f}",
    )
    col3.metric(
        "Worst product by WAPE",
        worst_row["product_name"],
        f"{worst_row['wape']:.3f}",
    )

    metric_columns = [
        "product_name",
        "method",
        "mae",
        "wape",
        "interpretation",
    ]
    if "is_selected_method" in metrics.columns:
        metric_columns.append("is_selected_method")
    st.dataframe(metrics[metric_columns].round(3), use_container_width=True)


def show_sales_signals(signals_df, selected_product):
    st.header("Sales Signals")
    st.write(
        "Raw sales notes are converted into structured demand signals such as "
        "expected quantity, probability, period, risk factors, and signal type."
    )

    signals = filter_by_product(signals_df, selected_product)
    signal_columns = [
        "source_note_text",
        "expected_quantity_kg",
        "intent_probability",
        "expected_period",
        "risk_factors",
        "signal_type",
    ]
    st.dataframe(signals[signal_columns], use_container_width=True)


def show_material_risk(material_risk_df, selected_product):
    st.header("Material Risk")
    st.write(
        "Adjusted demand is converted into PET requirement and compared with "
        "available inventory after safety stock. Negative shortage/surplus means "
        "shortage risk."
    )
    st.write(
        "Risk levels are based on shortage ratio, not just whether shortage "
        "exists. Priority rank shows which products have the largest expected "
        "PET shortage."
    )
    st.caption(
        "shortage_or_surplus_kg = available_after_safety_kg - required_pet_kg"
    )

    material_risk = filter_by_product(material_risk_df, selected_product)
    risk_columns = [
        "product_name",
        "adjusted_forecast_kg",
        "required_pet_kg",
        "available_after_safety_kg",
        "shortage_kg",
        "coverage_ratio",
        "shortage_ratio",
        "risk_level",
        "priority_rank",
    ]
    missing_risk_columns = [
        column for column in risk_columns if column not in material_risk.columns
    ]
    if missing_risk_columns:
        st.warning(
            "material_risk.csv is missing expected risk columns: "
            f"{', '.join(missing_risk_columns)}. "
            "Re-run supply planning with: "
            "venv\\Scripts\\python.exe -m src.supply_planning"
        )
        available_risk_columns = [
            column for column in risk_columns if column in material_risk.columns
        ]
        if available_risk_columns:
            st.dataframe(
                material_risk[available_risk_columns],
                use_container_width=True,
            )
    else:
        st.dataframe(material_risk[risk_columns], use_container_width=True)

    chart_data = material_risk.set_index("product_name")

    st.subheader("Forecast Comparison")
    st.bar_chart(chart_data[["baseline_forecast_kg", "adjusted_forecast_kg"]])

    st.subheader("PET Requirement vs Availability")
    st.bar_chart(chart_data[["required_pet_kg", "available_after_safety_kg"]])

    st.subheader("Shortage / Surplus")
    st.bar_chart(chart_data["shortage_or_surplus_kg"])


def safe_ratio(numerator, denominator):
    if pd.isna(denominator) or denominator <= 0:
        return 0
    return numerator / denominator


def get_scenario_risk_level(shortage_kg, shortage_ratio):
    if pd.isna(shortage_kg) or shortage_kg == 0:
        return "ok"
    if shortage_ratio >= 0.50:
        return "critical_shortage"
    if shortage_ratio >= 0.25:
        return "high_shortage"
    if shortage_ratio >= 0.10:
        return "medium_shortage"
    return "low_shortage"


def show_scenario_analysis(material_risk_df, selected_product):
    st.header("Scenario Analysis")
    st.write(
        "Scenario Analysis lets the user test how demand changes or "
        "stronger/weaker sales signals affect PET requirement and shortage risk."
    )
    st.caption(
        "scenario_adjusted_forecast_kg = "
        "(baseline_forecast_kg + scenario_sales_signal_adjustment_kg) "
        "* demand_change_factor"
    )
    st.caption(
        "scenario_shortage_or_surplus_kg = "
        "available_after_safety_kg - scenario_required_pet_kg. "
        "If the shortage/surplus value is negative, there is a shortage."
    )

    demand_change_percent = st.slider(
        "Demand change percent",
        min_value=-30,
        max_value=50,
        value=0,
        step=5,
    )
    intent_adjustment_percent = st.slider(
        "Intent adjustment percent",
        min_value=-30,
        max_value=30,
        value=0,
        step=5,
    )

    scenario = filter_by_product(material_risk_df, selected_product).copy()
    demand_multiplier = 1 + (demand_change_percent / 100)
    intent_multiplier = 1 + (intent_adjustment_percent / 100)

    scenario["scenario_sales_signal_adjustment_kg"] = (
        scenario["sales_signal_adjustment_kg"] * intent_multiplier
    )
    scenario["scenario_adjusted_forecast_kg"] = (
        scenario["baseline_forecast_kg"]
        + scenario["scenario_sales_signal_adjustment_kg"]
    ) * demand_multiplier
    scenario["scenario_required_pet_kg"] = (
        scenario["scenario_adjusted_forecast_kg"] * scenario["kg_pet_per_kg_product"]
    )
    scenario["scenario_shortage_or_surplus_kg"] = (
        scenario["available_after_safety_kg"] - scenario["scenario_required_pet_kg"]
    )
    scenario["scenario_shortage_kg"] = scenario[
        "scenario_shortage_or_surplus_kg"
    ].apply(lambda value: abs(value) if value < 0 else 0)
    scenario["scenario_shortage_ratio"] = scenario.apply(
        lambda row: safe_ratio(
            row["scenario_shortage_kg"],
            row["scenario_required_pet_kg"],
        ),
        axis=1,
    )
    scenario["scenario_risk_level"] = scenario.apply(
        lambda row: get_scenario_risk_level(
            row["scenario_shortage_kg"],
            row["scenario_shortage_ratio"],
        ),
        axis=1,
    )

    scenario_columns = [
        "product_name",
        "baseline_forecast_kg",
        "sales_signal_adjustment_kg",
        "scenario_sales_signal_adjustment_kg",
        "adjusted_forecast_kg",
        "scenario_adjusted_forecast_kg",
        "required_pet_kg",
        "scenario_required_pet_kg",
        "available_after_safety_kg",
        "scenario_shortage_or_surplus_kg",
        "scenario_risk_level",
    ]

    col1, col2 = st.columns(2)
    col1.metric(
        "Total scenario required PET kg",
        f"{scenario['scenario_required_pet_kg'].sum():,.0f}",
    )
    col2.metric(
        "Products with shortage risk",
        f"{(scenario['scenario_risk_level'] != 'ok').sum():,}",
    )
    st.dataframe(scenario[scenario_columns].round(2), use_container_width=True)


def main():
    st.set_page_config(page_title="Demand Intelligence MVP", layout="wide")
    st.title("Demand Intelligence MVP Dashboard")
    st.write(
        "This dashboard shows the MVP value loop: historical sales and extracted "
        "sales signals are used to create an adjusted forecast, estimate PET "
        "requirement, and identify shortage/surplus risk."
    )
    st.caption("Simple dashboard for existing MVP pipeline outputs.")

    data = load_dashboard_data()
    orders_df = data["orders"]
    forecast_df = data["forecast"]
    forecast_metrics_df = data["forecast_metrics"]
    signals_df = data["signals"]
    material_risk_df = data["material_risk"]

    product_names = sorted(material_risk_df["product_name"].dropna().unique())
    selected_product = st.sidebar.selectbox(
        "Product filter",
        ["All products"] + product_names,
    )

    show_overview(orders_df, material_risk_df, signals_df)
    show_forecast(forecast_df, material_risk_df, selected_product)
    show_forecast_evaluation(forecast_metrics_df, selected_product)
    show_sales_signals(signals_df, selected_product)
    show_material_risk(material_risk_df, selected_product)
    show_scenario_analysis(material_risk_df, selected_product)


if __name__ == "__main__":
    main()
