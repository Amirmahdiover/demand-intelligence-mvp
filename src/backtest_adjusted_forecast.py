from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_loader import load_orders, load_products
from src.forecast import aggregate_weekly_demand
from src.supply_planning import (
    calculate_controlled_signal_adjustment,
    get_signal_timing_confidence,
    get_timing_confidence_weight,
)


SIGNALS_PATH = ROOT_DIR / "outputs" / "signals" / "extracted_sales_signals.csv"
OUTPUT_DIR = ROOT_DIR / "outputs" / "forecast"
BACKTEST_OUTPUT_PATH = OUTPUT_DIR / "adjusted_forecast_backtest.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "adjusted_forecast_backtest_summary.csv"

TEST_WEEK_COUNT = 12
BASELINE_WINDOW = 4

BACKTEST_COLUMNS = [
    "product_id",
    "product_name",
    "test_week",
    "actual_demand_kg",
    "baseline_forecast_kg",
    "raw_signal_adjustment_kg",
    "controlled_signal_adjustment_kg",
    "adjusted_forecast_kg",
    "baseline_abs_error",
    "adjusted_abs_error",
    "baseline_error_pct",
    "adjusted_error_pct",
    "improvement_kg",
    "improvement_pct",
    "adjusted_better_than_baseline",
    "notes_count_used",
    "capped_flag",
]

SUMMARY_COLUMNS = [
    "product_id",
    "product_name",
    "test_weeks",
    "baseline_mae",
    "adjusted_mae",
    "baseline_wape",
    "adjusted_wape",
    "wape_delta",
    "adjusted_better_weeks",
    "adjusted_worse_weeks",
    "neutral_weeks",
]


def safe_divide(numerator, denominator):
    if pd.isna(denominator) or denominator == 0:
        return np.nan
    return numerator / denominator


def week_start_after(date_value, weeks_after=1):
    note_date = pd.Timestamp(date_value).normalize()
    note_week = note_date.to_period("W-FRI").start_time
    return note_week + pd.Timedelta(days=7 * weeks_after)


def load_extracted_signals():
    if not SIGNALS_PATH.exists():
        return pd.DataFrame(
            columns=[
                "note_id",
                "note_date",
                "product_id",
                "expected_quantity_kg",
                "expected_period",
                "intent_probability",
            ]
        )

    signals = pd.read_csv(SIGNALS_PATH)
    signals["note_date"] = pd.to_datetime(signals["note_date"], errors="coerce")
    signals["expected_quantity_kg"] = pd.to_numeric(
        signals["expected_quantity_kg"], errors="coerce"
    )
    signals["intent_probability"] = pd.to_numeric(
        signals["intent_probability"], errors="coerce"
    )
    signals["expected_period"] = signals["expected_period"].fillna("unknown")

    required = ["note_date", "product_id", "expected_quantity_kg", "intent_probability"]
    return signals.dropna(subset=required).copy()


def target_weeks_for_signal(note_date, expected_period, candidate_weeks):
    candidate_weeks = pd.DatetimeIndex(candidate_weeks)
    candidate_set = set(candidate_weeks)
    note_date = pd.Timestamp(note_date).normalize()
    expected_period = expected_period if pd.notna(expected_period) else "unknown"

    if expected_period == "next_week":
        target_week = week_start_after(note_date, weeks_after=1)
        return [target_week] if target_week in candidate_set else []

    if expected_period == "in_2_weeks":
        target_week = week_start_after(note_date, weeks_after=2)
        return [target_week] if target_week in candidate_set else []

    if expected_period == "this_month":
        note_month = note_date.to_period("M")
        return [
            week
            for week in candidate_weeks
            if week > note_date and week.to_period("M") == note_month
        ]

    if expected_period == "next_month":
        target_month = note_date.to_period("M") + 1
        return [
            week
            for week in candidate_weeks
            if week > note_date and week.to_period("M") == target_month
        ]

    target_week = week_start_after(note_date, weeks_after=1)
    return [target_week] if target_week in candidate_set else []


def build_signal_adjustments(signals, product_test_weeks):
    adjustment_rows = []

    for signal_index, signal in signals.iterrows():
        product_id = signal["product_id"]
        if product_id not in product_test_weeks:
            continue

        target_weeks = target_weeks_for_signal(
            signal["note_date"],
            signal["expected_period"],
            product_test_weeks[product_id],
        )
        target_weeks = [
            target_week
            for target_week in target_weeks
            if pd.Timestamp(signal["note_date"]) < target_week
        ]
        if not target_weeks:
            continue

        raw_total = signal["expected_quantity_kg"] * signal["intent_probability"]
        raw_per_week = raw_total / len(target_weeks)
        timing_confidence = get_signal_timing_confidence(signal["expected_period"])
        timing_weight = get_timing_confidence_weight(timing_confidence)
        note_id = signal.get("note_id", signal_index)

        for target_week in target_weeks:
            adjustment_rows.append(
                {
                    "product_id": product_id,
                    "test_week": target_week,
                    "note_id": note_id,
                    "raw_signal_adjustment_kg": raw_per_week,
                    "timing_weighted_signal_adjustment_kg": raw_per_week
                    * timing_weight,
                }
            )

    if not adjustment_rows:
        return pd.DataFrame(
            columns=[
                "product_id",
                "test_week",
                "raw_signal_adjustment_kg",
                "timing_weighted_signal_adjustment_kg",
                "notes_count_used",
            ]
        )

    adjustments = pd.DataFrame(adjustment_rows)
    return (
        adjustments.groupby(["product_id", "test_week"], as_index=False)
        .agg(
            raw_signal_adjustment_kg=("raw_signal_adjustment_kg", "sum"),
            timing_weighted_signal_adjustment_kg=(
                "timing_weighted_signal_adjustment_kg",
                "sum",
            ),
            notes_count_used=("note_id", "nunique"),
        )
        .copy()
    )


def baseline_from_history(weekly_demand, test_week):
    history = weekly_demand[weekly_demand.index < test_week]
    if history.empty:
        return 0.0

    return float(max(history.tail(BASELINE_WINDOW).mean(), 0))


def build_backtest():
    orders = load_orders()
    products = load_products()
    signals = load_extracted_signals()

    product_weekly_demand = {}
    product_test_weeks = {}

    for product in products.itertuples(index=False):
        weekly = aggregate_weekly_demand(orders, product.product_id)
        test_weeks = weekly[weekly > 0].tail(TEST_WEEK_COUNT).index

        product_weekly_demand[product.product_id] = weekly
        product_test_weeks[product.product_id] = list(test_weeks)

    signal_adjustments = build_signal_adjustments(signals, product_test_weeks)
    if not signal_adjustments.empty:
        signal_adjustments = signal_adjustments.set_index(["product_id", "test_week"])

    rows = []
    for product in products.itertuples(index=False):
        weekly = product_weekly_demand[product.product_id]

        for test_week in product_test_weeks[product.product_id]:
            actual_demand_kg = float(weekly.loc[test_week])
            baseline_forecast_kg = baseline_from_history(weekly, test_week)

            raw_signal_adjustment_kg = 0.0
            timing_weighted_adjustment_kg = 0.0
            notes_count_used = 0
            adjustment_key = (product.product_id, test_week)
            if not signal_adjustments.empty and adjustment_key in signal_adjustments.index:
                adjustment = signal_adjustments.loc[adjustment_key]
                raw_signal_adjustment_kg = float(adjustment["raw_signal_adjustment_kg"])
                timing_weighted_adjustment_kg = float(
                    adjustment["timing_weighted_signal_adjustment_kg"]
                )
                notes_count_used = int(adjustment["notes_count_used"])

            controlled_signal_adjustment_kg = float(
                calculate_controlled_signal_adjustment(
                    timing_weighted_adjustment_kg,
                    baseline_forecast_kg,
                )
            )
            adjusted_forecast_kg = baseline_forecast_kg + controlled_signal_adjustment_kg
            baseline_abs_error = abs(actual_demand_kg - baseline_forecast_kg)
            adjusted_abs_error = abs(actual_demand_kg - adjusted_forecast_kg)
            improvement_kg = baseline_abs_error - adjusted_abs_error

            rows.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "test_week": test_week,
                    "actual_demand_kg": actual_demand_kg,
                    "baseline_forecast_kg": baseline_forecast_kg,
                    "raw_signal_adjustment_kg": raw_signal_adjustment_kg,
                    "controlled_signal_adjustment_kg": controlled_signal_adjustment_kg,
                    "adjusted_forecast_kg": adjusted_forecast_kg,
                    "baseline_abs_error": baseline_abs_error,
                    "adjusted_abs_error": adjusted_abs_error,
                    "baseline_error_pct": safe_divide(
                        baseline_abs_error, actual_demand_kg
                    ),
                    "adjusted_error_pct": safe_divide(
                        adjusted_abs_error, actual_demand_kg
                    ),
                    "improvement_kg": improvement_kg,
                    "improvement_pct": safe_divide(improvement_kg, baseline_abs_error),
                    "adjusted_better_than_baseline": adjusted_abs_error
                    < baseline_abs_error,
                    "notes_count_used": notes_count_used,
                    "capped_flag": abs(
                        controlled_signal_adjustment_kg
                        - timing_weighted_adjustment_kg
                    )
                    > 1e-9,
                }
            )

    backtest = pd.DataFrame(rows, columns=BACKTEST_COLUMNS)
    backtest["test_week"] = pd.to_datetime(backtest["test_week"]).dt.date
    return backtest


def build_summary(backtest):
    rows = []

    for (product_id, product_name), product_rows in backtest.groupby(
        ["product_id", "product_name"], sort=True
    ):
        total_actual = product_rows["actual_demand_kg"].sum()
        baseline_wape = safe_divide(
            product_rows["baseline_abs_error"].sum(), total_actual
        )
        adjusted_wape = safe_divide(
            product_rows["adjusted_abs_error"].sum(), total_actual
        )
        adjusted_better = (
            product_rows["adjusted_abs_error"] < product_rows["baseline_abs_error"]
        )
        adjusted_worse = (
            product_rows["adjusted_abs_error"] > product_rows["baseline_abs_error"]
        )

        rows.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "test_weeks": len(product_rows),
                "baseline_mae": product_rows["baseline_abs_error"].mean(),
                "adjusted_mae": product_rows["adjusted_abs_error"].mean(),
                "baseline_wape": baseline_wape,
                "adjusted_wape": adjusted_wape,
                "wape_delta": adjusted_wape - baseline_wape,
                "adjusted_better_weeks": int(adjusted_better.sum()),
                "adjusted_worse_weeks": int(adjusted_worse.sum()),
                "neutral_weeks": int((~adjusted_better & ~adjusted_worse).sum()),
            }
        )

    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def describe_result(summary, baseline_wape, adjusted_wape):
    improved_products = (summary["wape_delta"] < 0).sum()
    worsened_products = (summary["wape_delta"] > 0).sum()

    if improved_products and worsened_products:
        return "mixed"
    if adjusted_wape < baseline_wape:
        return "improved"
    if adjusted_wape > baseline_wape:
        return "worsened"
    return "neutral"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    backtest = build_backtest()
    summary = build_summary(backtest)

    backtest.to_csv(BACKTEST_OUTPUT_PATH, index=False)
    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False)

    total_actual = backtest["actual_demand_kg"].sum()
    baseline_wape = safe_divide(backtest["baseline_abs_error"].sum(), total_actual)
    adjusted_wape = safe_divide(backtest["adjusted_abs_error"].sum(), total_actual)
    result = describe_result(summary, baseline_wape, adjusted_wape)

    print("Adjusted forecast retrospective backtest complete.")
    print(f"Tested rows: {len(backtest)}")
    print(f"Baseline average WAPE: {baseline_wape:.4f}")
    print(f"Adjusted average WAPE: {adjusted_wape:.4f}")
    print(f"Adjusted result: {result}")
    print(f"Backtest output: {BACKTEST_OUTPUT_PATH}")
    print(f"Summary output: {SUMMARY_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
