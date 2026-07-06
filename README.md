# Demand Intelligence MVP

## Project Description

A practical MVP for connecting historical sales, unstructured sales notes, market factors, and PET Chips inventory into demand and supply planning insight.

## Core Problem

The factory sees real demand too late because many early demand signals stay inside sales conversations and informal notes instead of entering planning workflows.

## MVP Value Loop

Sales Orders + Sales Notes + Market Factors
→ Demand Forecast
→ Adjusted Forecast using Sales Signals
→ PET Chips Requirement
→ Shortage / Surplus Risk
→ Decision Support

## Current Status

Day 2 and Day 3 — Data schema and synthetic data foundation.

## Completed So Far

- Project structure created
- Problem and scope documented
- Persian problem and scope document created
- Data schema defined
- CSV files defined
- Synthetic realistic data generator created
- Data loader utilities created
- Synthetic data logic documented

## Data Files

- `orders.csv`: Historical sales orders used as the main demand source.
- `customers.csv`: Customer information for customer, industry, city, size, and export analysis.
- `products.csv`: Product information and PET Chips conversion ratios.
- `sales_notes.csv`: Unstructured sales notes that may contain early demand signals.
- `market_factors.csv`: Weekly USD rate, PET price index, export condition, and season data.
- `inventory.csv`: PET Chips inventory, lead time, and safety stock.

## How to Generate Synthetic Data

```bash
python src/generate_synthetic_data.py
```

## How to Verify the Generated Files

After running the script, the `data/` folder should contain populated CSV files for orders, customers, products, sales notes, market factors, and inventory.

## Planned Next Steps

1. Perform EDA
2. Analyze monthly demand
3. Analyze demand by product and customer
4. Compare demand with USD rate and PET price index
5. Build baseline forecast
6. Extract structured sales signals from notes
7. Connect adjusted forecast to PET material risk
8. Build dashboard

## Limitations

Synthetic data is not proof of real industrial forecast accuracy. The first goal is to prove the data pipeline and decision-support loop. Real data will require cleaning, validation, and business feedback.
