from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def _read_csv(filename):
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Required data file not found: {path}. Run python src/generate_synthetic_data.py first."
        )
    return pd.read_csv(path)


def load_orders():
    return _read_csv("orders.csv")


def load_customers():
    return _read_csv("customers.csv")


def load_products():
    return _read_csv("products.csv")


def load_sales_notes():
    return _read_csv("sales_notes.csv")


def load_market_factors():
    return _read_csv("market_factors.csv")


def load_inventory():
    return _read_csv("inventory.csv")


def load_all_data():
    return {
        "orders": load_orders(),
        "customers": load_customers(),
        "products": load_products(),
        "sales_notes": load_sales_notes(),
        "market_factors": load_market_factors(),
        "inventory": load_inventory(),
    }
