# MVP Checkpoint

Status: Stable

Working value loop:
historical sales data
+ extracted sales signals
-> baseline forecast
-> adjusted forecast
-> PET requirement
-> shortage/surplus risk
-> Streamlit dashboard
-> scenario analysis

Confirmed outputs:
- outputs/forecast/product_forecasts.csv
- outputs/signals/extracted_sales_signals.csv
- outputs/planning/material_risk.csv

Dashboard sections:
- Overview
- Forecast
- Sales Signals
- Material Risk
- Scenario Analysis

Scenario validation:
- demand_change_percent changes scenario forecast, PET requirement, and shortage/surplus
- intent_adjustment_percent changes signal adjustment and scenario forecast
- scenario risk level is populated for all products

Run command:
python -m streamlit run app.py

Forecast Validation Notes:
- Time-based backtesting is used: training data comes from earlier periods and test data from later periods.
- No random shuffle split is used.
- Lag and rolling demand features use prior demand only.
- No future actual demand leakage was found.
- Market factors such as usd_rate, pet_price_index, and export_condition_index are treated as known, observed, or scenario/planning inputs for this MVP.
- Current WAPE results are MVP-level, not production-grade, and may be optimistic if future market factor values are not actually known at forecast time.

Known limitations:
- Synthetic data
- Simple baseline forecast
- Rule-based sales signal extraction
- Simplified scenario logic
- MVP dashboard, not polished enterprise UI
