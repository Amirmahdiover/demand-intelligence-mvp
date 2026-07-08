# Adjusted Forecast Evaluation Notes

Adjusted forecast accuracy cannot be evaluated reliably with the current MVP data.

## Current Adjusted Forecast Logic

- `outputs/forecast/period_adjusted_forecasts.csv` now stores adjusted forecasts at product-week level.
- `baseline_forecast_kg` comes from selected forecast rows in `outputs/forecast/product_forecasts.csv`.
- Sales signals are mapped to forecast weeks using `note_date` and `expected_period`.
- `sales_signal_adjustment_kg` is calculated as `expected_quantity_kg * intent_probability` and aggregated at product-week level.
- `adjusted_forecast_kg` is created as `baseline_forecast_kg + sales_signal_adjustment_kg`.
- `outputs/planning/material_risk.csv` still shows product-level totals, but those totals are aggregated from the period-level adjusted forecast rows.

## Why Evaluation Is Limited

- Actual order data is available through `2024-12-31`.
- Weekly aggregated actual demand ends at the week starting `2024-12-28`.
- Current forecast periods run from `2025-01-04` through `2025-02-22`.
- There is no actual demand available for those forecast periods in the current data.
- Sales signal timing is now mapped to forecast weeks, but there is still no actual demand for the mapped forecast weeks.

Because of this gap, calculating adjusted forecast WAPE against actuals would compare against unavailable future demand.

## Time-Safe Evaluation Requirement

A proper adjusted-vs-baseline evaluation would need:

- Historical forecast snapshots with a clear forecast creation date.
- Sales notes available only up to each forecast creation date.
- Actual demand for those target periods after the forecast creation date.
- Period-level baseline and adjusted forecasts so errors can be compared on matching periods. This structure now exists, but actual demand for those periods does not.

## Current Signal Impact Context

Current product-level signal adjustments are large enough that they should be treated carefully:

- P001: signal adjustment is about 19.2% of baseline forecast.
- P002: signal adjustment is about 34.1% of baseline forecast.
- P003: signal adjustment is about 7.9% of baseline forecast.
- P004: signal adjustment is about 32.2% of baseline forecast.
- P005: signal adjustment is about 42.2% of baseline forecast.

These signal impact ratios are not accuracy metrics. They only show how much the sales signal adjustment changes the selected baseline forecast.

## Conclusion

No adjusted forecast accuracy results were produced. The current MVP can show period-level planning impact from sales signals, but it should not claim that the adjusted forecast improves accuracy until period-aligned actual demand is available.
