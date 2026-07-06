# Synthetic Data Logic

## 1. Why Synthetic Data Is Needed

Real ERP and CRM data may not be available before the interview or early MVP stage. Realistic synthetic data allows the MVP pipeline to be built, tested, and demonstrated without waiting for company exports.

The synthetic data is not meant to prove real forecast accuracy. It is meant to prove that the project can connect orders, sales notes, market factors, product material ratios, and PET Chips inventory into a practical decision-support flow.

## 2. What the Synthetic Data Represents

The synthetic data represents:

- 24 months of sales orders
- 18 customers
- 5 products
- Weekly market factors
- Unstructured sales notes
- PET Chips inventory

Together, these files provide enough structure to prepare for Day 4 EDA and later baseline forecasting.

## 3. Realistic Patterns Included

The generated data includes practical business patterns:

- Large customers order more frequently and in larger quantities.
- Medium customers order moderate quantities.
- Small customers order less frequently.
- Some customers have seasonal demand patterns.
- Export-related customers are affected by USD rate and export conditions.
- PET price changes may shift demand timing.
- Product groups have different demand levels and PET conversion ratios.
- Some sales notes appear before real orders.
- Some sales notes are weak signals and never become official orders.

These patterns make the data more useful for demonstrating the MVP concept than purely random rows.

## 4. Limitations

Synthetic data cannot prove real industrial forecast accuracy. It is only used to prove the MVP pipeline and decision-support loop.

Real company data will require cleaning, validation, and business feedback. Common issues may include missing IDs, inconsistent product names, duplicated orders, incomplete notes, date errors, and inconsistent units.

## 5. Interview Talking Point

I used synthetic but realistic data so the project would not stop while waiting for real ERP/CRM exports. The goal is to prove the data pipeline and decision-support loop first, then replace synthetic data with real company data.
