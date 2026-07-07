# Demand Intelligence MVP

## Project Description

A practical Demand Intelligence MVP for connecting historical sales, unstructured sales notes, market factors, and PET Chips inventory into demand forecast and supply risk insight.

The current version is intentionally simple for a 2-week interview preparation MVP. It does not use FastAPI, a database, authentication, Docker, LLM APIs, advanced forecasting, or a professional UI yet.

## Project Execution Principle

This project follows a build-first approach.

The priority is to create a working end-to-end MVP pipeline before deeply studying or perfecting each file.

For each step, only check whether it runs, creates the expected output, and can be used by the next step. If it works well enough, move forward.

Do not deeply inspect rule-based logic, regex, architecture, or internal implementation details unless a real bug, broken output, or clearly wrong result appears.

When a problem appears, debug only the specific module and logic related to that problem.

The goal is:

Sales signals → adjusted forecast → PET requirement → shortage/surplus risk → decision-support output

A simple working pipeline is more valuable than a perfectly understood but unfinished project.

## Current MVP Status

The current MVP demonstrates an end-to-end demand intelligence loop:

Historical sales data
+ extracted sales signals
-> baseline forecast
-> adjusted forecast
-> PET requirement
-> shortage/surplus risk
-> Streamlit dashboard
-> scenario analysis

## Data Files

The synthetic data is stored in `data/`:

- `orders.csv`: historical sales orders used as the main demand source
- `customers.csv`: customer information for segment, industry, city, size, and export analysis
- `products.csv`: product information and PET Chips conversion ratios
- `sales_notes.csv`: unstructured sales notes that may contain early demand signals
- `market_factors.csv`: weekly USD rate, PET price index, export condition, and season data
- `inventory.csv`: PET Chips inventory, lead time, and safety stock

## How to Run

Install the minimal Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Optional: refresh the synthetic data:

```bash
python src/generate_synthetic_data.py
```

Run or refresh the MVP pipeline outputs:

```bash
python notebooks/02_forecast_baseline.py
python src/extract_sales_signals.py --method rule_based
python src/supply_planning.py
```

Expected output files:

- `outputs/forecast/product_forecasts.csv`
- `outputs/signals/extracted_sales_signals.csv`
- `outputs/planning/material_risk.csv`

Start the dashboard:

```bash
python -m streamlit run app.py
```

On Windows, `python -m streamlit run app.py` is safer than `streamlit run app.py` because the `streamlit` command may not be available on `PATH`.

## Dashboard Sections

- Overview: high-level dataset and risk summary
- Forecast: baseline and adjusted forecast
- Sales Signals: extracted structured signals from raw sales notes
- Material Risk: PET requirement and shortage/surplus risk
- Scenario Analysis: simple what-if analysis for demand and signal strength

## Run EDA

```bash
python notebooks/01_eda.py
```

This creates demand analysis charts in `outputs/charts/` and writes practical planning insights to `docs/eda_insights.md`.

## Current Limitations

- Data is synthetic.
- Forecasting is baseline/simple, not production-grade.
- Sales signal extraction is rule-based, not LLM-based yet.
- Scenario analysis is simplified.
- Inventory and PET assumptions are simplified.
- The dashboard is for MVP demonstration, not a polished enterprise UI.

## Next Possible Improvements

- Improve forecast evaluation and backtesting.
- Add better scenario controls.
- Replace rule-based extraction with LLM extraction.
- Add real ERP/CRM/Excel data ingestion.
- Improve dashboard charts and explanations.
- Add product/customer-level drilldowns.

## Project Structure

```text
demand-intelligence-mvp/
  data/
  docs/
  notebooks/
    01_eda.py
    02_forecast_baseline.py
  outputs/
    charts/
    forecast/
    planning/
    signals/
  app.py
  src/
    data_loader.py
    extract_sales_signals.py
    forecast.py
    generate_synthetic_data.py
    supply_planning.py
    utils.py
```
