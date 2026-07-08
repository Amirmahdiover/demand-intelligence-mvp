from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
FORECAST_PATH = ROOT_DIR / "outputs" / "forecast" / "product_forecasts.csv"
SIGNALS_PATH = ROOT_DIR / "outputs" / "signals" / "extracted_sales_signals.csv"
PRODUCTS_PATH = ROOT_DIR / "data" / "products.csv"
INVENTORY_PATH = ROOT_DIR / "data" / "inventory.csv"
PERIOD_ADJUSTED_FORECAST_PATH = (
    ROOT_DIR / "outputs" / "forecast" / "period_adjusted_forecasts.csv"
)
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
    "raw_sales_signal_adjustment_kg",
    "controlled_sales_signal_adjustment_kg",
    "raw_signal_impact_ratio",
    "controlled_signal_impact_ratio",
    "signal_adjustment_capped_flag",
    "high_signal_impact_warning",
    "signal_impact_ratio",
    "signal_impact_warning",
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
            "note_date",
            "expected_period",
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


def _get_forecast_week_column(forecast_df):
    if "forecast_period" in forecast_df.columns:
        return "forecast_period"
    if "week_start" in forecast_df.columns:
        return "week_start"
    raise ValueError("product_forecasts is missing forecast_period or week_start.")


def _prepare_forecast_rows(forecast_df):
    forecast_rows = forecast_df.copy()
    if "record_type" in forecast_rows.columns:
        forecast_rows = forecast_rows[forecast_rows["record_type"] == "forecast"].copy()

    forecast_week_column = _get_forecast_week_column(forecast_rows)
    forecast_rows["forecast_week"] = pd.to_datetime(
        forecast_rows[forecast_week_column],
        errors="coerce",
    )
    forecast_rows["baseline_forecast_kg"] = pd.to_numeric(
        forecast_rows["forecast_quantity_kg"],
        errors="coerce",
    ).fillna(0)

    if "selected_method" not in forecast_rows.columns:
        forecast_rows["selected_method"] = forecast_rows["method"]
    if "selected_method_wape" not in forecast_rows.columns:
        forecast_rows["selected_method_wape"] = pd.NA

    return forecast_rows.dropna(subset=["product_id", "forecast_week"])


def get_signal_timing_confidence(expected_period):
    if expected_period in {"next_week", "in_2_weeks"}:
        return "high"
    if expected_period in {"this_month", "next_month"}:
        return "medium"
    return "low"


def get_timing_confidence_weight(timing_confidence):
    weights = {
        "high": 1.00,
        "medium": 0.70,
        "low": 0.35,
    }
    return weights.get(timing_confidence, 0.35)


def summarize_signal_confidence(confidence_values):
    values = [value for value in confidence_values if pd.notna(value)]
    if not values:
        return "none"

    counts = pd.Series(values).value_counts()
    ordered_levels = ["high", "medium", "low"]
    return ", ".join(
        f"{level}:{int(counts[level])}"
        for level in ordered_levels
        if level in counts
    )


def calculate_controlled_signal_adjustment(timing_weighted_adjustment_kg, baseline_kg):
    if pd.isna(timing_weighted_adjustment_kg):
        return 0

    baseline_kg = 0 if pd.isna(baseline_kg) else float(baseline_kg)
    timing_weighted_adjustment_kg = float(timing_weighted_adjustment_kg)

    if timing_weighted_adjustment_kg >= 0:
        max_positive_adjustment = max(baseline_kg, 0) * 0.50
        return min(timing_weighted_adjustment_kg, max_positive_adjustment)

    max_negative_adjustment = -max(baseline_kg, 0)
    return max(timing_weighted_adjustment_kg, max_negative_adjustment)


def build_signal_control_note(row):
    if row["raw_sales_signal_adjustment_kg"] == 0:
        return "no adjustment"

    notes = ["raw adjustment preserved"]
    if row["timing_weighted_signal_adjustment_kg"] != row[
        "raw_sales_signal_adjustment_kg"
    ]:
        confidence_summary = str(row["signal_timing_confidence_summary"])
        if "low:" in confidence_summary:
            notes.append("low timing confidence reduced adjustment")
        elif "medium:" in confidence_summary:
            notes.append("medium timing confidence reduced adjustment")
        else:
            notes.append("timing confidence reduced adjustment")

    if row["signal_adjustment_capped_flag"]:
        notes.append("cap applied")

    return "; ".join(notes)


def _next_month_start(date_value):
    return (date_value.replace(day=1) + pd.DateOffset(months=1)).normalize()


def _target_weeks_for_signal(note_date, expected_period, forecast_weeks):
    forecast_weeks = pd.Series(pd.to_datetime(forecast_weeks).dropna().unique())
    forecast_weeks = forecast_weeks.sort_values().reset_index(drop=True)
    future_weeks = forecast_weeks[forecast_weeks > note_date]

    if expected_period == "next_week":
        return list(future_weeks.head(1))
    if expected_period == "in_2_weeks":
        if len(future_weeks) >= 2:
            return [future_weeks.iloc[1]]
        return []
    if expected_period == "this_month":
        target_weeks = forecast_weeks[
            (forecast_weeks > note_date)
            & (forecast_weeks.dt.year == note_date.year)
            & (forecast_weeks.dt.month == note_date.month)
        ]
        return list(target_weeks)
    if expected_period == "next_month":
        next_month = _next_month_start(note_date)
        target_weeks = forecast_weeks[
            (forecast_weeks.dt.year == next_month.year)
            & (forecast_weeks.dt.month == next_month.month)
        ]
        return list(target_weeks)

    return list(future_weeks.head(1))


def map_sales_signals_to_forecast_weeks(signals_df, forecast_rows):
    signals = signals_df.copy()
    signals = signals[signals["product_id"].notna()].copy()
    signals["note_date"] = pd.to_datetime(signals["note_date"], errors="coerce")
    signals["expected_quantity_kg"] = pd.to_numeric(
        signals["expected_quantity_kg"],
        errors="coerce",
    )
    signals["intent_probability"] = pd.to_numeric(
        signals["intent_probability"],
        errors="coerce",
    ).fillna(0)
    signals["expected_period"] = signals["expected_period"].fillna("unknown")
    signals = signals.dropna(subset=["note_date", "expected_quantity_kg"])

    forecast_weeks_by_product = {
        product_id: group["forecast_week"].sort_values().dropna().unique()
        for product_id, group in forecast_rows.groupby("product_id")
    }

    mapped_rows = []
    for signal in signals.itertuples(index=False):
        forecast_weeks = forecast_weeks_by_product.get(signal.product_id)
        if forecast_weeks is None or len(forecast_weeks) == 0:
            continue

        expected_period = str(signal.expected_period)
        target_weeks = _target_weeks_for_signal(
            signal.note_date,
            expected_period,
            forecast_weeks,
        )
        if not target_weeks:
            continue

        adjustment_kg = float(signal.expected_quantity_kg) * float(
            signal.intent_probability
        )
        adjustment_per_week = adjustment_kg / len(target_weeks)
        timing_confidence = get_signal_timing_confidence(expected_period)
        timing_weight = get_timing_confidence_weight(timing_confidence)

        for forecast_week in target_weeks:
            mapped_rows.append(
                {
                    "product_id": signal.product_id,
                    "forecast_week": forecast_week,
                    "raw_sales_signal_adjustment_kg": adjustment_per_week,
                    "timing_weighted_signal_adjustment_kg": (
                        adjustment_per_week * timing_weight
                    ),
                    "weighted_abs_signal_adjustment_kg": (
                        abs(adjustment_per_week) * timing_weight
                    ),
                    "abs_signal_adjustment_kg": abs(adjustment_per_week),
                    "signal_count": 1,
                    "signal_timing_confidence": timing_confidence,
                }
            )

    return pd.DataFrame(mapped_rows)


def build_period_adjusted_forecasts(forecast_df, signals_df):
    forecast_rows = _prepare_forecast_rows(forecast_df)
    baseline_columns = [
        "product_id",
        "product_name",
        "forecast_week",
        "baseline_forecast_kg",
        "selected_method",
        "selected_method_wape",
    ]
    period_forecast = forecast_rows[baseline_columns].copy()

    mapped_signals = map_sales_signals_to_forecast_weeks(signals_df, forecast_rows)
    if mapped_signals.empty:
        signal_adjustments = pd.DataFrame(
            columns=[
                "product_id",
                "forecast_week",
                "raw_sales_signal_adjustment_kg",
                "timing_weighted_signal_adjustment_kg",
                "weighted_abs_signal_adjustment_kg",
                "abs_signal_adjustment_kg",
                "signal_count",
                "signal_timing_confidence_summary",
            ]
        )
    else:
        signal_adjustments = (
            mapped_signals.groupby(["product_id", "forecast_week"], as_index=False)
            .agg(
                raw_sales_signal_adjustment_kg=(
                    "raw_sales_signal_adjustment_kg",
                    "sum",
                ),
                timing_weighted_signal_adjustment_kg=(
                    "timing_weighted_signal_adjustment_kg",
                    "sum",
                ),
                weighted_abs_signal_adjustment_kg=(
                    "weighted_abs_signal_adjustment_kg",
                    "sum",
                ),
                abs_signal_adjustment_kg=("abs_signal_adjustment_kg", "sum"),
                signal_count=("signal_count", "sum"),
                signal_timing_confidence_summary=(
                    "signal_timing_confidence",
                    summarize_signal_confidence,
                ),
            )
        )

    period_forecast = period_forecast.merge(
        signal_adjustments,
        on=["product_id", "forecast_week"],
        how="left",
    )
    signal_quantity_columns = [
        "raw_sales_signal_adjustment_kg",
        "timing_weighted_signal_adjustment_kg",
        "weighted_abs_signal_adjustment_kg",
        "abs_signal_adjustment_kg",
    ]
    period_forecast[signal_quantity_columns] = period_forecast[
        signal_quantity_columns
    ].fillna(0)
    period_forecast["signal_count"] = period_forecast["signal_count"].fillna(0).astype(int)
    period_forecast["signal_timing_confidence_summary"] = period_forecast[
        "signal_timing_confidence_summary"
    ].fillna("none")
    period_forecast["timing_confidence_weight"] = period_forecast.apply(
        lambda row: safe_ratio(
            row["weighted_abs_signal_adjustment_kg"],
            row["abs_signal_adjustment_kg"],
        ),
        axis=1,
    )
    period_forecast["raw_adjusted_forecast_kg"] = (
        period_forecast["baseline_forecast_kg"]
        + period_forecast["raw_sales_signal_adjustment_kg"]
    )
    period_forecast["max_positive_signal_adjustment_kg"] = (
        period_forecast["baseline_forecast_kg"].clip(lower=0) * 0.50
    )
    period_forecast["controlled_sales_signal_adjustment_kg"] = period_forecast.apply(
        lambda row: calculate_controlled_signal_adjustment(
            row["timing_weighted_signal_adjustment_kg"],
            row["baseline_forecast_kg"],
        ),
        axis=1,
    )
    period_forecast["adjusted_forecast_kg"] = (
        period_forecast["baseline_forecast_kg"]
        + period_forecast["controlled_sales_signal_adjustment_kg"]
    )
    period_forecast["raw_signal_impact_ratio"] = period_forecast.apply(
        lambda row: safe_ratio(
            row["raw_sales_signal_adjustment_kg"],
            row["baseline_forecast_kg"],
        ),
        axis=1,
    )
    period_forecast["controlled_signal_impact_ratio"] = period_forecast.apply(
        lambda row: safe_ratio(
            row["controlled_sales_signal_adjustment_kg"],
            row["baseline_forecast_kg"],
        ),
        axis=1,
    )
    period_forecast["signal_adjustment_capped_flag"] = (
        (
            period_forecast["controlled_sales_signal_adjustment_kg"]
            - period_forecast["timing_weighted_signal_adjustment_kg"]
        ).abs()
        > 0.000001
    )
    period_forecast["high_signal_impact_warning"] = (
        period_forecast["controlled_signal_impact_ratio"] > 0.40
    )
    period_forecast["signal_control_note"] = period_forecast.apply(
        build_signal_control_note,
        axis=1,
    )

    period_forecast = period_forecast.rename(
        columns={"forecast_week": "forecast_date"}
    )
    quantity_columns = [
        "baseline_forecast_kg",
        "raw_sales_signal_adjustment_kg",
        "raw_adjusted_forecast_kg",
        "timing_weighted_signal_adjustment_kg",
        "max_positive_signal_adjustment_kg",
        "controlled_sales_signal_adjustment_kg",
        "adjusted_forecast_kg",
    ]
    period_forecast[quantity_columns] = period_forecast[quantity_columns].round(2)
    ratio_columns = [
        "raw_signal_impact_ratio",
        "timing_confidence_weight",
        "controlled_signal_impact_ratio",
    ]
    period_forecast[ratio_columns] = period_forecast[ratio_columns].round(4)

    output_columns = [
        "product_id",
        "product_name",
        "forecast_date",
        "baseline_forecast_kg",
        "raw_sales_signal_adjustment_kg",
        "raw_signal_impact_ratio",
        "raw_adjusted_forecast_kg",
        "timing_confidence_weight",
        "timing_weighted_signal_adjustment_kg",
        "max_positive_signal_adjustment_kg",
        "controlled_sales_signal_adjustment_kg",
        "controlled_signal_impact_ratio",
        "adjusted_forecast_kg",
        "selected_method",
        "selected_method_wape",
        "signal_count",
        "signal_timing_confidence_summary",
        "signal_adjustment_capped_flag",
        "high_signal_impact_warning",
        "signal_control_note",
    ]
    return period_forecast[output_columns].sort_values(
        ["product_id", "forecast_date"]
    )


def aggregate_period_adjusted_forecasts(period_adjusted_df):
    period_forecast = period_adjusted_df.copy()
    period_forecast["baseline_forecast_kg"] = pd.to_numeric(
        period_forecast["baseline_forecast_kg"],
        errors="coerce",
    ).fillna(0)
    period_forecast["raw_sales_signal_adjustment_kg"] = pd.to_numeric(
        period_forecast["raw_sales_signal_adjustment_kg"],
        errors="coerce",
    ).fillna(0)
    period_forecast["controlled_sales_signal_adjustment_kg"] = pd.to_numeric(
        period_forecast["controlled_sales_signal_adjustment_kg"],
        errors="coerce",
    ).fillna(0)
    period_forecast["adjusted_forecast_kg"] = pd.to_numeric(
        period_forecast["adjusted_forecast_kg"],
        errors="coerce",
    ).fillna(0)

    totals = (
        period_forecast.groupby("product_id", as_index=False)
        .agg(
            baseline_forecast_kg=("baseline_forecast_kg", "sum"),
            raw_sales_signal_adjustment_kg=("raw_sales_signal_adjustment_kg", "sum"),
            controlled_sales_signal_adjustment_kg=(
                "controlled_sales_signal_adjustment_kg",
                "sum",
            ),
            adjusted_forecast_kg=("adjusted_forecast_kg", "sum"),
            baseline_method=("selected_method", "first"),
            signal_adjustment_capped_flag=("signal_adjustment_capped_flag", "max"),
        )
    )
    totals["sales_signal_adjustment_kg"] = totals[
        "controlled_sales_signal_adjustment_kg"
    ]
    totals["raw_signal_impact_ratio"] = totals.apply(
        lambda row: safe_ratio(
            row["raw_sales_signal_adjustment_kg"],
            row["baseline_forecast_kg"],
        ),
        axis=1,
    )
    totals["controlled_signal_impact_ratio"] = totals.apply(
        lambda row: safe_ratio(
            row["controlled_sales_signal_adjustment_kg"],
            row["baseline_forecast_kg"],
        ),
        axis=1,
    )
    totals["high_signal_impact_warning"] = (
        totals["controlled_signal_impact_ratio"] > 0.40
    )
    totals["signal_impact_ratio"] = totals["controlled_signal_impact_ratio"]
    totals["signal_impact_warning"] = totals["high_signal_impact_warning"]
    return totals


def aggregate_baseline_forecast(forecast_df, baseline_method=DEFAULT_BASELINE_METHOD):
    if "record_type" in forecast_df.columns:
        forecast_rows = forecast_df[forecast_df["record_type"] == "forecast"].copy()
    else:
        forecast_rows = forecast_df.copy()

    if "selected_method" not in forecast_rows.columns:
        forecast_rows = forecast_rows[forecast_rows["method"] == baseline_method].copy()

    if forecast_rows.empty:
        raise ValueError(
            f"No forecast rows found for baseline method '{baseline_method}'."
        )

    forecast_rows["forecast_quantity_kg"] = pd.to_numeric(
        forecast_rows["forecast_quantity_kg"],
        errors="coerce",
    ).fillna(0)

    baseline = (
        forecast_rows.groupby("product_id", as_index=False)
        .agg(
            baseline_forecast_kg=("forecast_quantity_kg", "sum"),
            baseline_method=(
                "selected_method" if "selected_method" in forecast_rows.columns else "method",
                "first",
            ),
        )
    )
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
    period_adjusted_df=None,
):
    if period_adjusted_df is not None:
        forecast_totals = aggregate_period_adjusted_forecasts(period_adjusted_df)
    else:
        baseline = aggregate_baseline_forecast(
            forecast_df,
            baseline_method=baseline_method,
        )
        adjustments = aggregate_sales_signal_adjustments(signals_df)
        forecast_totals = baseline.merge(adjustments, on="product_id", how="left")
        forecast_totals["sales_signal_adjustment_kg"] = forecast_totals[
            "sales_signal_adjustment_kg"
        ].fillna(0)
        forecast_totals["adjusted_forecast_kg"] = (
            forecast_totals["baseline_forecast_kg"]
            + forecast_totals["sales_signal_adjustment_kg"]
        )
        forecast_totals["raw_sales_signal_adjustment_kg"] = forecast_totals[
            "sales_signal_adjustment_kg"
        ]
        forecast_totals["controlled_sales_signal_adjustment_kg"] = forecast_totals[
            "sales_signal_adjustment_kg"
        ]
        forecast_totals["raw_signal_impact_ratio"] = forecast_totals.apply(
            lambda row: safe_ratio(
                row["raw_sales_signal_adjustment_kg"],
                row["baseline_forecast_kg"],
            ),
            axis=1,
        )
        forecast_totals["controlled_signal_impact_ratio"] = forecast_totals.apply(
            lambda row: safe_ratio(
                row["controlled_sales_signal_adjustment_kg"],
                row["baseline_forecast_kg"],
            ),
            axis=1,
        )
        forecast_totals["signal_adjustment_capped_flag"] = False
        forecast_totals["high_signal_impact_warning"] = (
            forecast_totals["controlled_signal_impact_ratio"] > 0.40
        )
        forecast_totals["signal_impact_ratio"] = forecast_totals[
            "controlled_signal_impact_ratio"
        ]
        forecast_totals["signal_impact_warning"] = forecast_totals[
            "high_signal_impact_warning"
        ]

    inventory = inventory_df.iloc[0]
    material_name = inventory["material_name"]
    current_inventory_kg = float(inventory["current_inventory_kg"])
    safety_stock_kg = float(inventory["safety_stock_kg"])
    available_after_safety_kg = current_inventory_kg - safety_stock_kg

    planning = products_df.merge(forecast_totals, on="product_id", how="left")
    planning["baseline_method"] = planning["baseline_method"].fillna(baseline_method)
    planning["baseline_forecast_kg"] = planning["baseline_forecast_kg"].fillna(0)
    planning["sales_signal_adjustment_kg"] = planning[
        "sales_signal_adjustment_kg"
    ].fillna(0)
    planning["raw_sales_signal_adjustment_kg"] = planning[
        "raw_sales_signal_adjustment_kg"
    ].fillna(0)
    planning["controlled_sales_signal_adjustment_kg"] = planning[
        "controlled_sales_signal_adjustment_kg"
    ].fillna(0)
    planning["adjusted_forecast_kg"] = planning["adjusted_forecast_kg"].fillna(
        planning["baseline_forecast_kg"] + planning["sales_signal_adjustment_kg"]
    )
    planning["raw_signal_impact_ratio"] = planning["raw_signal_impact_ratio"].fillna(0)
    planning["controlled_signal_impact_ratio"] = planning[
        "controlled_signal_impact_ratio"
    ].fillna(0)
    planning["signal_adjustment_capped_flag"] = planning[
        "signal_adjustment_capped_flag"
    ].fillna(False)
    planning["high_signal_impact_warning"] = planning[
        "high_signal_impact_warning"
    ].fillna(False)
    planning["signal_impact_ratio"] = planning["signal_impact_ratio"].fillna(0)
    planning["signal_impact_warning"] = planning["signal_impact_warning"].fillna(False)
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
        "raw_sales_signal_adjustment_kg",
        "controlled_sales_signal_adjustment_kg",
        "adjusted_forecast_kg",
        "required_pet_kg",
        "current_inventory_kg",
        "safety_stock_kg",
        "available_after_safety_kg",
        "shortage_or_surplus_kg",
        "shortage_kg",
    ]
    ratio_columns = [
        "coverage_ratio",
        "shortage_ratio",
        "raw_signal_impact_ratio",
        "controlled_signal_impact_ratio",
        "signal_impact_ratio",
    ]
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
    period_adjusted_df = build_period_adjusted_forecasts(forecast_df, signals_df)
    PERIOD_ADJUSTED_FORECAST_PATH.parent.mkdir(parents=True, exist_ok=True)
    period_adjusted_df.to_csv(PERIOD_ADJUSTED_FORECAST_PATH, index=False)

    material_risk_df = build_material_risk_plan(
        forecast_df,
        signals_df,
        products_df,
        inventory_df,
        baseline_method=baseline_method,
        period_adjusted_df=period_adjusted_df,
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
    print(f"Period adjusted forecast file: {PERIOD_ADJUSTED_FORECAST_PATH}")
    print(f"Output file: {output_path}")

    return material_risk_df


if __name__ == "__main__":
    run_supply_planning()
