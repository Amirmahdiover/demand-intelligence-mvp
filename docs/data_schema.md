# Demand Intelligence MVP — Data Schema

## 1. Purpose

This schema defines the minimum data needed to connect historical sales, customer behavior, product material requirements, unstructured sales signals, market factors, and PET Chips inventory risk.

The goal is not to model every ERP or CRM field. The goal is to create a practical data foundation for the MVP value loop:

Sales Orders + Sales Notes + Market Factors
→ Demand Forecast
→ Adjusted Forecast using Sales Signals
→ PET Chips Requirement
→ Shortage / Surplus Risk
→ Decision Support

## 2. Tables

### orders.csv

Stores historical sales orders. This is the main source for understanding past demand by date, customer, and product.

Why it matters:
Orders provide the baseline demand pattern that later forecasting and demand analysis will use.

Columns:

- `order_id`: Unique order identifier.
- `order_date`: Date when the order was placed.
- `customer_id`: Customer connected to the order.
- `product_id`: Product ordered by the customer.
- `quantity_kg`: Ordered quantity in kilograms.
- `unit_price`: Unit price for the ordered product.
- `delivery_date`: Expected or actual delivery date.
- `status`: Order status such as completed, delivered, cancelled, or pending.

### customers.csv

Stores customer information so demand can be analyzed by customer type, industry, location, and export dependency.

Why it matters:
Different customer groups may order at different frequencies, volumes, and sensitivity to market conditions.

Columns:

- `customer_id`: Unique customer identifier.
- `customer_name`: Customer company name.
- `industry`: Customer industry or business segment.
- `city`: Customer location.
- `customer_type`: Customer size group, such as large, medium, or small.
- `export_related`: Whether the customer is affected by export activity.

### products.csv

Stores product information and the material conversion ratio needed to convert product demand into PET Chips requirement.

Why it matters:
The MVP must connect demand forecast to raw material planning, so each product needs a PET consumption ratio.

Columns:

- `product_id`: Unique product identifier.
- `product_name`: Product name.
- `product_group`: Product category such as yarn, fiber, industrial, or carpet.
- `kg_pet_per_kg_product`: Kilograms of PET Chips required for one kilogram of finished product.

### sales_notes.csv

Stores unstructured sales notes that may contain early demand signals before official orders.

Why it matters:
Sales notes are a key differentiator of this MVP because they may reveal demand earlier than order records.

Columns:

- `note_id`: Unique note identifier.
- `note_date`: Date when the note was recorded.
- `customer_id`: Customer related to the note.
- `salesperson`: Salesperson who recorded the note.
- `note_text`: Unstructured sales note text.

### market_factors.csv

Stores external market factors that may affect demand, such as USD rate, PET price, export conditions, and season.

Why it matters:
Market conditions can influence customer timing, order size, export demand, and raw material planning risk.

Columns:

- `date`: Date of the market factor observation.
- `usd_rate`: USD exchange rate indicator.
- `pet_price_index`: PET price index.
- `export_condition_index`: Export condition indicator, where higher values represent better export conditions.
- `season`: Season for the observation date.

### inventory.csv

Stores PET Chips inventory, lead time, and safety stock for shortage/surplus risk calculation.

Why it matters:
The MVP must translate demand into material requirement and compare that requirement with available PET Chips inventory.

Columns:

- `material_name`: Material name, currently PET Chips.
- `current_inventory_kg`: Current available inventory in kilograms.
- `lead_time_days`: Expected material lead time in days.
- `safety_stock_kg`: Minimum safety stock target in kilograms.

## 3. Relationships

- `orders.customer_id` connects to `customers.customer_id`.
- `orders.product_id` connects to `products.product_id`.
- `sales_notes.customer_id` connects to `customers.customer_id`.
- `products.kg_pet_per_kg_product` converts product demand into PET Chips requirement.
- `market_factors.date` can be connected to `order_date` or `note_date`.
- `inventory` provides current PET Chips stock, lead time, and safety stock.

## 4. MVP Data Flow

orders.csv + customers.csv + products.csv
→ historical demand by customer and product

sales_notes.csv
→ early unstructured demand signals

market_factors.csv
→ external context such as USD rate, PET price, export condition, and season

forecast demand + product material ratio + inventory
→ PET Chips requirement
→ shortage/surplus risk

## 5. Notes for Future Real Data

In a real implementation:

- Orders may come from ERP or Excel exports.
- Sales notes may come from CRM, spreadsheets, WhatsApp summaries, or manual salesperson notes.
- Market factors may come from internal files or external sources.
- Inventory may come from procurement or warehouse data.
- Data quality issues should be expected, such as missing customer IDs, inconsistent product names, duplicate orders, incomplete notes, and inconsistent units.

The first version should keep the schema simple enough to build and explain, while still realistic enough to support the MVP decision loop.
