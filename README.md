# Demand Intelligence MVP

## Project Description

A practical Demand Intelligence MVP for connecting historical sales, unstructured sales notes, market factors, and PET Chips inventory into demand forecast and supply risk insight.

The current version is intentionally simple for a 2-week interview preparation MVP. It does not use FastAPI, a database, authentication, Docker, LLM APIs, advanced forecasting, or a professional UI yet.

## MVP Value Loop

Sales Orders + Sales Notes + Market Factors
-> Demand Forecast
-> Adjusted Forecast using Sales Signals
-> PET Chips Requirement
-> Shortage / Surplus Risk
-> Decision Support

## Current Status

Day 1 to Day 5 are now covered at MVP level.

- Day 1-3: project structure, problem scope, schema, synthetic data, data loader utilities
- Day 4: exploratory demand analysis with charts and planning insights
- Day 5: weekly baseline forecast by product with simple forecast metrics

## Data Files

The synthetic data is stored in `data/`:

- `orders.csv`: historical sales orders used as the main demand source
- `customers.csv`: customer information for segment, industry, city, size, and export analysis
- `products.csv`: product information and PET Chips conversion ratios
- `sales_notes.csv`: unstructured sales notes that may contain early demand signals
- `market_factors.csv`: weekly USD rate, PET price index, export condition, and season data
- `inventory.csv`: PET Chips inventory, lead time, and safety stock

## Setup

Install the minimal Python dependencies:

```bash
pip install -r requirements.txt
```

## Generate Synthetic Data

```bash
python src/generate_synthetic_data.py
```

This refreshes the CSV files in `data/`.

## Run EDA

Open and run the notebook:

```bash
jupyter notebook notebooks/01_eda.ipynb
```

Or run the reproducible script version:

```bash
python notebooks/01_eda.py
```

This creates demand analysis charts in `outputs/charts/` and writes practical planning insights to `docs/eda_insights.md`.

Day 4 EDA demonstrates:

- Monthly total demand
- Demand by product
- Demand by customer
- Top customers by total quantity
- Demand volatility by product
- PET price index vs demand
- USD rate vs demand
- Export-related vs non-export demand comparison

## Run Baseline Forecast

```bash
python notebooks/02_forecast_baseline.py
```

This runs simple weekly product-level forecasts and saves:

- `outputs/forecast/product_forecasts.csv`
- `outputs/forecast/forecast_metrics.csv`
- `outputs/charts/baseline_forecast_actual_vs_forecast.png`

Day 5 baseline forecast demonstrates:

- Weekly demand aggregation
- Naive forecast function
- Moving average forecast function
- Simple exponential smoothing function when `statsmodels` is installed
- Backtest metrics using MAE and WAPE
- Forecast output for the next 8 weeks per product

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
  src/
    data_loader.py
    forecast.py
    generate_synthetic_data.py
    utils.py
```

## Limitations

Synthetic data is not proof of real industrial forecast accuracy. The current forecast is a baseline planning reference, not a production forecasting system. Real company data will require cleaning, validation, business feedback, and comparison against actual planning decisions.
