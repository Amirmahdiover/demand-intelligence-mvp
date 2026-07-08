# Demo Script

Use this short flow to demo the MVP as a decision-support loop, not as a production forecasting system.

## Setup

Run the dashboard:

```bash
python -m streamlit run app.py
```

## Demo Flow

1. Show historical sales data.
   Explain that `data/orders.csv` is the demand history used to build weekly product-level forecasts.

2. Show the baseline forecast.
   In the Forecast section, explain that the selected baseline method per product comes from historical backtesting WAPE.

3. Show sales notes.
   Open the Sales Signals section and explain that raw sales notes represent early customer demand signals.

4. Show extracted structured sales signals.
   Point to expected quantity, intent probability, expected period, risk factors, and signal type.

5. Show raw vs controlled signal adjustment.
   Use `outputs/forecast/period_adjusted_forecasts.csv` to explain that raw adjustments are preserved, then timing confidence weights and a weekly cap produce controlled adjustments for planning.

6. Show the adjusted forecast.
   Explain that `adjusted_forecast_kg` uses controlled signal adjustments, not raw unbounded signal totals.

7. Show PET Chips requirement.
   In Material Risk, explain that adjusted forecast is converted into PET requirement using product material ratios.

8. Show shortage/surplus risk.
   Point to shortage, coverage ratio, shortage ratio, risk level, and priority rank.

9. Show scenario analysis.
   Adjust demand and intent sliders to show how planning risk changes under simple what-if assumptions.

10. Close with the credibility boundary.
    This MVP does not claim industrial forecast accuracy. Baseline forecast accuracy is evaluated only with historical backtesting. Adjusted forecast accuracy is not claimed because actual demand is not available for the future forecast weeks. The demo proves the decision-support loop from demand signals to material risk.

## Key Message

The value is early visibility: sales notes and historical demand are converted into a controlled planning signal that helps procurement and production see PET Chips risk before orders become urgent.
