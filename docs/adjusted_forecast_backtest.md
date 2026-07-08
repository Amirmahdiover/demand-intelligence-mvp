# Retrospective Adjusted Forecast Backtest

## Purpose

This backtest checks whether historical sales signal adjustments would have improved baseline forecasts on periods where actual demand is already known.

It does not evaluate future adjusted forecast weeks. Future adjusted forecasts remain decision-support scenario outputs because actual demand is not available for those periods yet.

## Methodology

- Script: `src/backtest_adjusted_forecast.py`
- Output detail: `outputs/forecast/adjusted_forecast_backtest.csv`
- Output summary: `outputs/forecast/adjusted_forecast_backtest_summary.csv`
- Test window: last 12 nonzero historical demand weeks per product
- Baseline: 4-week moving average using only demand before each test week
- Signals: pre-extracted sales signals from `outputs/signals/extracted_sales_signals.csv`
- Timing rule: signals are mapped to historical product-weeks from `note_date` and `expected_period`
- Leakage control: a signal is used only when `note_date` is before the tested week
- Guardrail: the same timing confidence weights and controlled adjustment cap from `src/supply_planning.py` are applied

## Current Results

- Tested rows: 60 product-weeks
- Backtest weeks: 2024-08-24 to 2024-12-28
- Future forecast weeks begin after the historical backtest period
- Baseline WAPE: 0.6361
- Adjusted WAPE: 0.6377
- Result: mixed by product, with overall adjusted WAPE slightly worse

Product summary:

| Product | Baseline WAPE | Adjusted WAPE | Result |
| --- | ---: | ---: | --- |
| Polyester Yarn 150D | 0.6956 | 0.6956 | neutral |
| Polyester Yarn 300D | 0.6440 | 0.6440 | neutral |
| Industrial Polyester Fiber | 0.6031 | 0.5977 | improved |
| Carpet Polyester Yarn | 0.6094 | 0.6094 | neutral |
| High Tenacity Polyester Yarn | 0.6431 | 0.6591 | worsened |

## Limitations

- The data is synthetic.
- Only a small number of tested product-weeks had usable historical signal adjustments.
- This evaluates the current rule-based signal adjustment structure, not a new forecasting model.
- The result should not be presented as proof that adjusted forecasts are more accurate.
- The framework is now in place for future tuning of signal timing, weighting, and confidence rules.
