from pathlib import Path
import argparse
import re

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs" / "signals"
DEFAULT_OUTPUT_PATH = OUTPUT_DIR / "extracted_sales_signals.csv"

SIGNAL_COLUMNS = [
    "note_id",
    "note_date",
    "customer_id",
    "product_id",
    "product_name",
    "expected_quantity_kg",
    "expected_period",
    "intent_probability",
    "risk_factors",
    "signal_type",
    "extraction_method",
    "extraction_confidence",
    "source_note_text",
]

ALLOWED_EXPECTED_PERIODS = {
    "next_week",
    "in_2_weeks",
    "this_month",
    "next_month",
    "soon",
    "unknown",
}
ALLOWED_SIGNAL_TYPES = {
    "possible_order",
    "confirmed_order_signal",
    "delayed_or_cancelled",
    "market_risk_signal",
}
SUPPORTED_EXTRACTION_METHODS = {"rule_based", "llm"}

DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

QUANTITY_PATTERN = re.compile(
    r"(?P<quantity>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>kg|kgs|kilogram|kilograms|ton|tons|tonne|tonnes|کیلوگرم|کیلو|تن)",
    re.IGNORECASE,
)

EXPECTED_PERIOD_PATTERNS = [
    ("in_2_weeks", ["in two weeks", "2 weeks", "دو هفته"]),
    ("next_week", ["next week", "هفته آینده"]),
    ("next_month", ["next month", "ماه آینده"]),
    ("this_month", ["this month", "این ماه"]),
    ("soon", ["soon", "به زودی"]),
]

NEGATIVE_INTENT_PHRASES = [
    "cancel",
    "cancelled",
    "canceled",
    "delayed",
    "postponed",
    "on hold",
    "عقب انداخته",
    "متوقف",
    "به تعویق",
    "لغو",
]

STRONG_INTENT_PHRASES = [
    "confirmed",
    "will order",
    "agreed",
    "definitely",
    "قطعی شد",
    "قطعا",
]

LIKELY_INTENT_PHRASES = [
    "likely",
    "probably",
    "plans to",
    "expected to",
    "احتمالا",
    "احتمال دارد",
    "نهایی می‌کند",
    "نهایی میکند",
    "سفارش می‌دهد",
    "سفارش میدهد",
    "رو به پایان",
]

MEDIUM_INTENT_PHRASES = [
    "may",
    "might",
    "considering",
    "possibly",
    "شاید",
    "احتمالی",
    "ممکن",
    "موکول",
]

WEAK_INTENT_PHRASES = [
    "asked",
    "interested",
    "quote",
    "pricing",
    "price",
    "قیمت خواست",
    "سؤال کرد",
    "سوال کرد",
    "پرسید",
    "مقایسه قیمت",
    "بررسی کرد",
    "قیمت",
]

RISK_FACTOR_RULES = [
    (
        "PET price",
        ["pet", "raw material", "polyester chips", "مواد اولیه", "پت"],
    ),
    (
        "currency",
        ["usd", "exchange rate", "currency", "dollar", "دلار", "نرخ ارز", "ارز"],
    ),
    (
        "export condition",
        ["export", "foreign customer", "international", "صادرات", "صادراتی", "خارجی"],
    ),
    (
        "seasonality",
        ["season", "summer", "winter", "spring", "autumn", "فصل", "تابستان", "زمستان", "بهار", "پاییز"],
    ),
    (
        "supply delay",
        ["delay", "lead time", "import", "shipment", "تاخیر", "تأخیر", "زمان تحویل", "واردات", "محموله"],
    ),
]

GENERIC_PRODUCT_TERMS = {
    "polyester",
    "yarn",
    "fiber",
    "product",
}


def _normalize_text(note_text):
    if pd.isna(note_text):
        return ""
    return str(note_text).translate(DIGIT_TRANSLATION).lower()


def _contains_any(text, phrases):
    for phrase in phrases:
        if phrase.isascii():
            pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
            if re.search(pattern, text):
                return True
        elif phrase in text:
            return True
    return False


def _is_missing(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return bool(pd.isna(value))


def _has_intent_signal(note_text):
    text = _normalize_text(note_text)
    intent_phrase_groups = [
        NEGATIVE_INTENT_PHRASES,
        STRONG_INTENT_PHRASES,
        LIKELY_INTENT_PHRASES,
        MEDIUM_INTENT_PHRASES,
        WEAK_INTENT_PHRASES,
    ]
    return any(_contains_any(text, phrases) for phrases in intent_phrase_groups)


def _normalize_risk_factors(risk_factors):
    if isinstance(risk_factors, list):
        return "|".join(str(value) for value in risk_factors if not _is_missing(value))
    if _is_missing(risk_factors):
        return ""
    return str(risk_factors)


def _parse_number(number_text):
    normalized_number = number_text.translate(DIGIT_TRANSLATION).replace(",", "")
    return float(normalized_number)


def extract_quantity_kg(note_text):
    text = _normalize_text(note_text)
    match = QUANTITY_PATTERN.search(text)
    if match is None:
        return np.nan

    quantity = _parse_number(match.group("quantity"))
    unit = match.group("unit").lower()

    if unit in {"ton", "tons", "tonne", "tonnes", "تن"}:
        quantity *= 1000

    return float(quantity)


def extract_expected_period(note_text):
    text = _normalize_text(note_text)
    for expected_period, phrases in EXPECTED_PERIOD_PATTERNS:
        if _contains_any(text, phrases):
            return expected_period
    return "unknown"


def extract_intent_probability(note_text):
    text = _normalize_text(note_text)

    if _contains_any(text, NEGATIVE_INTENT_PHRASES):
        return 0.2
    if _contains_any(text, STRONG_INTENT_PHRASES):
        return 0.9
    if _contains_any(text, LIKELY_INTENT_PHRASES):
        return 0.7
    if _contains_any(text, MEDIUM_INTENT_PHRASES):
        return 0.5
    if _contains_any(text, WEAK_INTENT_PHRASES):
        return 0.4
    return 0.5


def extract_risk_factors(note_text):
    text = _normalize_text(note_text)
    risk_factors = []

    for risk_factor, phrases in RISK_FACTOR_RULES:
        if _contains_any(text, phrases):
            risk_factors.append(risk_factor)

    return "|".join(risk_factors)


def extract_signal_type(note_text, intent_probability, risk_factors, expected_quantity_kg):
    text = _normalize_text(note_text)

    if _contains_any(text, NEGATIVE_INTENT_PHRASES):
        return "delayed_or_cancelled"
    if intent_probability >= 0.9:
        return "confirmed_order_signal"
    if risk_factors and pd.isna(expected_quantity_kg):
        return "market_risk_signal"
    return "possible_order"


def calculate_rule_based_confidence(
    note_text,
    product_id,
    expected_quantity_kg,
    risk_factors,
):
    has_product = not _is_missing(product_id)
    has_quantity = not _is_missing(expected_quantity_kg)

    if has_product and has_quantity:
        return 0.85
    if has_product or has_quantity:
        return 0.65
    if risk_factors or _has_intent_signal(note_text):
        return 0.45
    return 0.5


def detect_product(note_text, products_df):
    text = _normalize_text(note_text)

    for product in products_df.itertuples(index=False):
        product_name = getattr(product, "product_name")
        if _normalize_text(product_name) in text:
            return getattr(product, "product_id"), product_name

    best_match = None
    best_score = 0

    for product in products_df.itertuples(index=False):
        product_name = getattr(product, "product_name")
        normalized_product_name = _normalize_text(product_name)
        terms = [
            term
            for term in re.split(r"[^a-z0-9]+", normalized_product_name)
            if term and term not in GENERIC_PRODUCT_TERMS
        ]
        score = sum(1 for term in terms if term in text)

        if score > best_score:
            best_match = (getattr(product, "product_id"), product_name)
            best_score = score

    if best_match is None:
        return np.nan, np.nan

    return best_match


def _find_product_by_name(product_name, products_df):
    if _is_missing(product_name):
        return np.nan, np.nan

    normalized_product_name = _normalize_text(product_name)
    for product in products_df.itertuples(index=False):
        canonical_name = getattr(product, "product_name")
        if _normalize_text(canonical_name) == normalized_product_name:
            return getattr(product, "product_id"), canonical_name

    return np.nan, np.nan


def validate_extracted_signal(signal, products_df):
    validated_signal = dict(signal)
    validated_signal["risk_factors"] = _normalize_risk_factors(
        validated_signal.get("risk_factors", "")
    )

    intent_probability = float(validated_signal.get("intent_probability"))
    if not 0 <= intent_probability <= 1:
        raise ValueError("intent_probability must be between 0 and 1.")
    validated_signal["intent_probability"] = intent_probability

    extraction_confidence = float(validated_signal.get("extraction_confidence"))
    if not 0 <= extraction_confidence <= 1:
        raise ValueError("extraction_confidence must be between 0 and 1.")
    validated_signal["extraction_confidence"] = extraction_confidence

    expected_period = validated_signal.get("expected_period", "unknown")
    if expected_period not in ALLOWED_EXPECTED_PERIODS:
        allowed_values = ", ".join(sorted(ALLOWED_EXPECTED_PERIODS))
        raise ValueError(
            f"expected_period must be one of: {allowed_values}. "
            f"Got: {expected_period}."
        )

    signal_type = validated_signal.get("signal_type")
    if signal_type not in ALLOWED_SIGNAL_TYPES:
        allowed_values = ", ".join(sorted(ALLOWED_SIGNAL_TYPES))
        raise ValueError(
            f"signal_type must be one of: {allowed_values}. Got: {signal_type}."
        )

    quantity = validated_signal.get("expected_quantity_kg")
    if _is_missing(quantity):
        validated_signal["expected_quantity_kg"] = np.nan
    else:
        validated_signal["expected_quantity_kg"] = float(quantity)

    product_id = validated_signal.get("product_id")
    product_name = validated_signal.get("product_name")
    matched_product_id, matched_product_name = _find_product_by_name(
        product_name,
        products_df,
    )

    if not _is_missing(product_name) and _is_missing(matched_product_name):
        raise ValueError(
            f"product_name must match products.csv when provided. Got: {product_name}."
        )

    if not _is_missing(matched_product_name):
        validated_signal["product_id"] = matched_product_id
        validated_signal["product_name"] = matched_product_name
    elif not _is_missing(product_id):
        valid_product_ids = set(products_df["product_id"].dropna().astype(str))
        if str(product_id) not in valid_product_ids:
            raise ValueError(
                f"product_id must match products.csv when provided. Got: {product_id}."
            )

    return validated_signal


def build_llm_extraction_prompt(note_text, products_df):
    product_names = "\n".join(
        f"- {product_name}"
        for product_name in products_df["product_name"].dropna().astype(str).tolist()
    )

    return f"""You are extracting structured demand signals from a sales note.

Available product names:
{product_names}

Rules:
- Do not invent product names.
- If no product is clear, return null.
- If no quantity is clear, return null.
- Return JSON only.

Extract strict JSON with this schema:
{{
  "product_name": string or null,
  "expected_quantity_kg": number or null,
  "expected_period": "next_week" | "in_2_weeks" | "this_month" | "next_month" | "soon" | "unknown",
  "intent_probability": number between 0 and 1,
  "risk_factors": list of strings,
  "signal_type": "possible_order" | "confirmed_order_signal" | "delayed_or_cancelled" | "market_risk_signal",
  "extraction_confidence": number between 0 and 1
}}

Sales note:
{note_text}
"""


def extract_signal_llm(note_row, products_df):
    raise NotImplementedError(
        "LLM extraction is not implemented yet. Use method='rule_based' for the "
        "current MVP, or connect an LLM provider later."
    )


def extract_signal_rule_based(note_row, products_df):
    note_text = note_row.get("note_text", "")
    expected_quantity_kg = extract_quantity_kg(note_text)
    expected_period = extract_expected_period(note_text)
    intent_probability = extract_intent_probability(note_text)
    risk_factors = extract_risk_factors(note_text)
    product_id, product_name = detect_product(note_text, products_df)
    signal_type = extract_signal_type(
        note_text,
        intent_probability,
        risk_factors,
        expected_quantity_kg,
    )
    extraction_confidence = calculate_rule_based_confidence(
        note_text,
        product_id,
        expected_quantity_kg,
        risk_factors,
    )

    signal = {
        "note_id": note_row.get("note_id", np.nan),
        "note_date": note_row.get("note_date", np.nan),
        "customer_id": note_row.get("customer_id", np.nan),
        "product_id": product_id,
        "product_name": product_name,
        "expected_quantity_kg": expected_quantity_kg,
        "expected_period": expected_period,
        "intent_probability": intent_probability,
        "risk_factors": risk_factors,
        "signal_type": signal_type,
        "extraction_method": "rule_based",
        "extraction_confidence": extraction_confidence,
        "source_note_text": note_text,
    }

    return validate_extracted_signal(signal, products_df)


def extract_signal_from_note(note_row, products_df, method="rule_based"):
    if method == "rule_based":
        return extract_signal_rule_based(note_row, products_df)
    if method == "llm":
        return extract_signal_llm(note_row, products_df)

    allowed_methods = ", ".join(sorted(SUPPORTED_EXTRACTION_METHODS))
    raise ValueError(f"Unknown extraction method '{method}'. Use one of: {allowed_methods}.")


def extract_all_sales_signals(sales_notes_df, products_df, method="rule_based"):
    rows = [
        extract_signal_from_note(note_row, products_df, method=method)
        for _, note_row in sales_notes_df.iterrows()
    ]
    return pd.DataFrame(rows, columns=SIGNAL_COLUMNS)


def _validate_columns(df, required_columns, table_name):
    missing_columns = set(required_columns).difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: {sorted(missing_columns)}"
        )


def run_sales_signal_extraction(
    sales_notes_path=DATA_DIR / "sales_notes.csv",
    products_path=DATA_DIR / "products.csv",
    output_path=DEFAULT_OUTPUT_PATH,
    method="rule_based",
):
    method = method.lower()
    if method not in SUPPORTED_EXTRACTION_METHODS:
        allowed_methods = ", ".join(sorted(SUPPORTED_EXTRACTION_METHODS))
        raise ValueError(
            f"Unknown extraction method '{method}'. Use one of: {allowed_methods}."
        )

    sales_notes_df = pd.read_csv(sales_notes_path)
    products_df = pd.read_csv(products_path)

    _validate_columns(
        sales_notes_df,
        {"note_id", "note_date", "customer_id", "note_text"},
        "sales_notes",
    )
    _validate_columns(products_df, {"product_id", "product_name"}, "products")

    signals_df = extract_all_sales_signals(sales_notes_df, products_df, method=method)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    signals_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    signals_with_quantity = signals_df["expected_quantity_kg"].notna().sum()
    signals_with_product = signals_df["product_id"].notna().sum()
    average_intent = signals_df["intent_probability"].mean()

    print("Sales signal extraction complete.")
    print(f"Extraction method: {method}")
    print(f"Notes processed: {len(signals_df)}")
    print(f"Signals with quantity: {signals_with_quantity}")
    print(f"Signals with product detected: {signals_with_product}")
    print(f"Average intent probability: {average_intent:.2f}")
    print(f"Output file: {output_path}")

    return signals_df


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Extract structured demand signals from sales notes."
    )
    parser.add_argument(
        "--method",
        choices=sorted(SUPPORTED_EXTRACTION_METHODS),
        default="rule_based",
        help="Extraction method to use. The current MVP default is rule_based.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_sales_signal_extraction(method=args.method)
