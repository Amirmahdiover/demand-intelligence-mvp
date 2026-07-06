# -*- coding: utf-8 -*-
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 72
RNG = np.random.default_rng(SEED)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def season_for_date(value):
    month = pd.Timestamp(value).month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def fa_number(value):
    return str(int(round(value))).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def quantity_phrase(quantity_kg):
    rounded_kg = int(round(quantity_kg / 500) * 500)
    if rounded_kg >= 10000 and RNG.random() < 0.7:
        return f"حدود {fa_number(rounded_kg / 1000)} تن"
    return f"حدود {fa_number(rounded_kg)} کیلو"


def generate_customers():
    rows = [
        ("C001", "Atlas Carpet Industries", "Carpet Manufacturing", "Kashan", "large", True),
        ("C002", "Pars Export Textiles", "Export Trading", "Tehran", "large", True),
        ("C003", "Negin Industrial Fabrics", "Industrial Fabrics", "Isfahan", "large", False),
        ("C004", "Shahin Yarn Manufacturing", "Textile Manufacturing", "Yazd", "large", True),
        ("C005", "Mehr Home Textiles", "Home Textiles", "Mashhad", "medium", False),
        ("C006", "Sepahan Polyester Co", "Textile Manufacturing", "Isfahan", "medium", False),
        ("C007", "Kavir Carpet Weaving", "Carpet Manufacturing", "Yazd", "medium", True),
        ("C008", "Tabriz Auto Textile", "Automotive Textiles", "Tabriz", "medium", False),
        ("C009", "Arman Export Group", "Export Trading", "Tehran", "medium", True),
        ("C010", "Shiraz Technical Fabrics", "Industrial Fabrics", "Shiraz", "medium", False),
        ("C011", "Qom Home Fabric", "Home Textiles", "Qom", "medium", False),
        ("C012", "Kashan Rug Materials", "Carpet Manufacturing", "Kashan", "small", True),
        ("C013", "Yazd Yarn Workshop", "Textile Manufacturing", "Yazd", "small", False),
        ("C014", "Rayan Textile Supplies", "Export Trading", "Tehran", "small", True),
        ("C015", "Mashhad Weaving House", "Home Textiles", "Mashhad", "small", False),
        ("C016", "Taban Industrial Cloth", "Industrial Fabrics", "Tabriz", "small", False),
        ("C017", "Nika Carpet Yarn", "Carpet Manufacturing", "Kashan", "small", False),
        ("C018", "Dena Export Fabrics", "Export Trading", "Shiraz", "small", True),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "customer_id",
            "customer_name",
            "industry",
            "city",
            "customer_type",
            "export_related",
        ],
    )


def generate_products():
    rows = [
        ("P001", "Polyester Yarn 150D", "yarn", 1.05),
        ("P002", "Polyester Yarn 300D", "yarn", 1.07),
        ("P003", "Industrial Polyester Fiber", "industrial", 1.08),
        ("P004", "Carpet Polyester Yarn", "carpet", 1.04),
        ("P005", "High Tenacity Polyester Yarn", "fiber", 1.10),
    ]
    return pd.DataFrame(
        rows,
        columns=["product_id", "product_name", "product_group", "kg_pet_per_kg_product"],
    )


def generate_market_factors():
    dates = pd.date_range("2023-01-01", "2024-12-31", freq="W-SUN")
    n_rows = len(dates)

    trend = np.linspace(42000, 62000, n_rows)
    cycle = 1300 * np.sin(np.linspace(0, 4 * np.pi, n_rows))
    cumulative_noise = np.cumsum(RNG.normal(0, 180, n_rows))
    usd_rate = trend + cycle + cumulative_noise + RNG.normal(0, 650, n_rows)
    usd_rate = np.maximum(usd_rate, 39000)

    usd_index = usd_rate / usd_rate[0]
    pet_price_index = 100 + ((usd_index - 1) * 58) + np.linspace(0, 12, n_rows)
    pet_price_index += 4 * np.sin(np.linspace(0, 6 * np.pi, n_rows))
    pet_price_index += RNG.normal(0, 2.2, n_rows)

    export_condition_index = 1 + 0.15 * np.sin(np.linspace(0.4, 5 * np.pi, n_rows))
    export_condition_index += RNG.normal(0, 0.06, n_rows)
    export_condition_index = np.clip(export_condition_index, 0.7, 1.3)

    return pd.DataFrame(
        {
            "date": dates,
            "usd_rate": np.round(usd_rate, 0).astype(int),
            "pet_price_index": np.round(pet_price_index, 2),
            "export_condition_index": np.round(export_condition_index, 2),
            "season": [season_for_date(date) for date in dates],
        }
    )


def product_weights_for_customer(industry):
    weights_by_industry = {
        "Carpet Manufacturing": [0.12, 0.18, 0.05, 0.55, 0.10],
        "Textile Manufacturing": [0.36, 0.32, 0.08, 0.16, 0.08],
        "Industrial Fabrics": [0.10, 0.18, 0.44, 0.06, 0.22],
        "Home Textiles": [0.28, 0.34, 0.08, 0.22, 0.08],
        "Export Trading": [0.26, 0.24, 0.16, 0.22, 0.12],
        "Automotive Textiles": [0.08, 0.18, 0.32, 0.04, 0.38],
    }
    return np.array(weights_by_industry[industry])


def generate_orders(customers, products, market_factors):
    rows = []
    product_ids = products["product_id"].to_numpy()
    base_prices = {
        "P001": 1.35,
        "P002": 1.48,
        "P003": 1.62,
        "P004": 1.42,
        "P005": 1.88,
    }
    product_quantity_multiplier = {
        "P001": 1.00,
        "P002": 0.95,
        "P003": 0.78,
        "P004": 1.12,
        "P005": 0.72,
    }
    customer_bias = {
        row.customer_id: RNG.uniform(0.88, 1.16) for row in customers.itertuples(index=False)
    }
    seasonal_peak = {
        "C001": "autumn",
        "C002": "spring",
        "C004": "summer",
        "C005": "winter",
        "C007": "autumn",
        "C009": "spring",
        "C012": "autumn",
        "C018": "summer",
    }
    type_probability = {"large": 0.78, "medium": 0.50, "small": 0.25}
    type_quantity = {
        "small": (1000, 2600, 5000),
        "medium": (5000, 9500, 15000),
        "large": (15000, 26000, 40000),
    }
    type_discount = {"large": 0.94, "medium": 0.98, "small": 1.02}
    statuses = ["completed", "delivered", "cancelled", "pending"]
    status_probability = [0.54, 0.36, 0.04, 0.06]

    previous_pet_index = market_factors["pet_price_index"].iloc[0]

    for market in market_factors.itertuples(index=False):
        market_date = pd.Timestamp(market.date)
        pet_delta = market.pet_price_index - previous_pet_index
        usd_pressure = (market.usd_rate - market_factors["usd_rate"].median()) / market_factors[
            "usd_rate"
        ].median()

        for customer in customers.itertuples(index=False):
            probability = type_probability[customer.customer_type] * customer_bias[customer.customer_id]

            if seasonal_peak.get(customer.customer_id) == market.season:
                probability *= 1.22
            elif market.season == "winter":
                probability *= 0.94

            if customer.export_related:
                export_effect = 0.90 + (0.22 * market.export_condition_index)
                usd_effect = 1 - max(usd_pressure, 0) * 0.18
                probability *= np.clip(export_effect * usd_effect, 0.72, 1.18)

            # When PET prices rise, some customers pull demand forward before another increase.
            if pet_delta > 1.4:
                probability *= 1.12
            elif pet_delta < -1.8:
                probability *= 0.95

            probability = min(probability, 0.92)

            if RNG.random() >= probability:
                continue

            order_count = 1
            if customer.customer_type == "large" and RNG.random() < 0.22:
                order_count = 2
            elif customer.customer_type == "medium" and RNG.random() < 0.08:
                order_count = 2

            for _ in range(order_count):
                product_id = RNG.choice(product_ids, p=product_weights_for_customer(customer.industry))
                low, mode, high = type_quantity[customer.customer_type]
                quantity = RNG.triangular(low, mode, high)

                if seasonal_peak.get(customer.customer_id) == market.season:
                    quantity *= RNG.uniform(1.10, 1.35)
                if customer.export_related:
                    quantity *= np.clip(0.82 + (0.24 * market.export_condition_index), 0.82, 1.18)
                if pet_delta > 1.4:
                    quantity *= RNG.uniform(1.05, 1.18)

                quantity *= product_quantity_multiplier[product_id]
                quantity_kg = int(round(quantity / 100) * 100)

                order_date = market_date + timedelta(days=int(RNG.integers(0, 7)))
                order_date = min(order_date, pd.Timestamp("2024-12-31"))
                delivery_date = order_date + timedelta(days=int(RNG.integers(7, 31)))

                unit_price = base_prices[product_id] * (market.pet_price_index / 100)
                unit_price *= type_discount[customer.customer_type]
                unit_price *= RNG.normal(1.0, 0.035)

                rows.append(
                    {
                        "order_id": f"O{len(rows) + 1:06d}",
                        "order_date": order_date,
                        "customer_id": customer.customer_id,
                        "product_id": product_id,
                        "quantity_kg": max(quantity_kg, 800),
                        "unit_price": round(unit_price, 2),
                        "delivery_date": delivery_date,
                        "status": RNG.choice(statuses, p=status_probability),
                    }
                )

        previous_pet_index = market.pet_price_index

    orders = pd.DataFrame(rows)
    orders = orders.sort_values(["order_date", "order_id"]).reset_index(drop=True)
    orders["order_id"] = [f"O{i + 1:06d}" for i in range(len(orders))]
    return orders


def generate_sales_notes(customers, products, orders):
    rows = []
    salespeople = ["Ali", "Reza", "Sara", "Neda", "Hamid"]
    product_lookup = products.set_index("product_id")["product_name"].to_dict()
    customer_lookup = customers.set_index("customer_id").to_dict("index")

    eligible_orders = orders[pd.to_datetime(orders["order_date"]) >= pd.Timestamp("2023-02-01")]
    linked_orders = eligible_orders.sample(n=55, random_state=SEED).reset_index(drop=True)
    timing_options = ["هفته آینده", "دو هفته دیگر", "ماه آینده", "آخر فصل"]

    for order in linked_orders.itertuples(index=False):
        days_before = int(RNG.integers(14, 29))
        note_date = pd.Timestamp(order.order_date) - timedelta(days=days_before)
        note_date = max(note_date, pd.Timestamp("2023-01-01"))
        product_name = product_lookup[order.product_id]
        qty = quantity_phrase(order.quantity_kg * RNG.uniform(0.85, 1.10))
        timing = RNG.choice(timing_options)
        customer = customer_lookup[order.customer_id]

        strong_templates = [
            f"مشتری {order.customer_id} گفت اگر قیمت PET بیشتر نشود، احتمالا {timing} {qty} {product_name} سفارش می‌دهد.",
            f"در پیگیری امروز، مشتری {order.customer_id} برای {qty} {product_name} قیمت خواست و گفت تصمیم خرید را برای {timing} نهایی می‌کند.",
            f"مشتری {order.customer_id} برای برنامه تولید جدید درباره {qty} {product_name} سؤال کرد و سفارش رسمی را به تایید مدیریت موکول کرد.",
            f"با مشتری {order.customer_id} صحبت شد؛ به دلیل نگرانی از نرخ دلار، احتمال دارد خرید {qty} {product_name} را جلو بیندازد.",
            f"مشتری {order.customer_id} گفت موجودی فعلی رو به پایان است و اگر شرایط پرداخت تایید شود، {timing} {qty} سفارش می‌دهد.",
        ]
        if customer["export_related"]:
            strong_templates.append(
                f"مشتری {order.customer_id} برای پروژه صادراتی درباره {qty} {product_name} پرسید، اما گفت وضعیت صادرات هنوز قطعی نیست."
            )

        rows.append(
            {
                "note_id": f"N{len(rows) + 1:04d}",
                "note_date": note_date,
                "customer_id": order.customer_id,
                "salesperson": RNG.choice(salespeople),
                "note_text": RNG.choice(strong_templates),
            }
        )

    weak_templates = [
        "مشتری {customer_id} فقط برای مقایسه قیمت {product_name} تماس گرفت و هنوز برنامه خرید مشخصی ندارد.",
        "مشتری {customer_id} گفت به خاطر نوسان نرخ دلار فعلا تصمیم خرید را عقب انداخته اما برای آخر فصل نیاز احتمالی دارد.",
        "مشتری {customer_id} درباره قیمت PET پرسید و گفت اگر بازار آرام شود شاید ماه آینده خرید کند.",
        "مشتری {customer_id} برای {quantity} {product_name} سؤال کرد ولی هنوز سفارش قطعی نداده است.",
        "مشتری {customer_id} گفت اگر سفارش صادراتی خودش تایید شود، احتمالا دو هفته دیگر {quantity} نیاز دارد.",
        "فروشنده با مشتری {customer_id} تماس گرفت؛ مشتری فعلا موجودی کافی دارد اما قیمت‌ها را برای تصمیم بعدی دنبال می‌کند.",
        "مشتری {customer_id} درخواست quote برای {product_name} داشت ولی تاکید کرد خرید قطعی نیست.",
        "مشتری {customer_id} گفت اگر موجودی فعلی تمام شود، هفته آینده درباره {quantity} دوباره تماس می‌گیرد.",
        "مشتری {customer_id} به خاطر شرایط صادرات تصمیم را متوقف کرده اما برای پروژه جدید احتمال مصرف دارد.",
        "مشتری {customer_id} فقط زمان تحویل و قیمت را بررسی کرد؛ سیگنال ضعیف است و هنوز به سفارش رسمی نزدیک نیست.",
    ]

    random_dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    for _ in range(50):
        customer = customers.sample(n=1, random_state=int(RNG.integers(1, 100000))).iloc[0]
        product = products.sample(n=1, random_state=int(RNG.integers(1, 100000))).iloc[0]
        qty = quantity_phrase(RNG.choice([4000, 6000, 8000, 12000, 15000, 20000]))
        template = RNG.choice(weak_templates)
        rows.append(
            {
                "note_id": f"N{len(rows) + 1:04d}",
                "note_date": RNG.choice(random_dates),
                "customer_id": customer["customer_id"],
                "salesperson": RNG.choice(salespeople),
                "note_text": template.format(
                    customer_id=customer["customer_id"],
                    product_name=product["product_name"],
                    quantity=qty,
                ),
            }
        )

    notes = pd.DataFrame(rows)
    notes = notes.sort_values(["note_date", "note_id"]).reset_index(drop=True)
    notes["note_id"] = [f"N{i + 1:04d}" for i in range(len(notes))]
    return notes


def generate_inventory():
    return pd.DataFrame(
        [
            {
                "material_name": "PET Chips",
                "current_inventory_kg": int(RNG.integers(85000, 140001)),
                "lead_time_days": int(RNG.integers(35, 71)),
                "safety_stock_kg": int(RNG.integers(20000, 40001)),
            }
        ]
    )


def save_csv(dataframe, filename, date_columns=None):
    output = dataframe.copy()
    for column in date_columns or []:
        output[column] = pd.to_datetime(output[column]).dt.strftime("%Y-%m-%d")
    output.to_csv(DATA_DIR / filename, index=False, encoding="utf-8-sig")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    customers = generate_customers()
    products = generate_products()
    market_factors = generate_market_factors()
    orders = generate_orders(customers, products, market_factors)
    sales_notes = generate_sales_notes(customers, products, orders)
    inventory = generate_inventory()

    save_csv(customers, "customers.csv")
    save_csv(products, "products.csv")
    save_csv(market_factors, "market_factors.csv", ["date"])
    save_csv(orders, "orders.csv", ["order_date", "delivery_date"])
    save_csv(sales_notes, "sales_notes.csv", ["note_date"])
    save_csv(inventory, "inventory.csv")

    print("Synthetic data generated successfully:")
    print(f"- customers: {len(customers)}")
    print(f"- products: {len(products)}")
    print(f"- market factor rows: {len(market_factors)}")
    print(f"- orders: {len(orders)}")
    print(f"- sales notes: {len(sales_notes)}")
    print(f"- inventory rows: {len(inventory)}")


if __name__ == "__main__":
    main()
