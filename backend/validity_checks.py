# validity_checks.py
import pandas as pd
from difflib import get_close_matches
from value_utils import present_values, decimal_number
from type_inference import EMAIL_PATTERN, CURRENCY_PATTERN

# ============== EXISTING CHECKS ==============

def check_email_validity(df: pd.DataFrame, col: str) -> dict:
    values = present_values(df[col]).astype(str)
    values = values[values.str.strip() != ""]
    invalid_mask = ~values.str.match(EMAIL_PATTERN)
    invalid = values[invalid_mask]
    return {
        "check": "invalid_email", "column": col, "count": int(invalid_mask.sum()),
        "pct": round(100 * invalid_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": invalid.index.tolist(), "examples": invalid.head(3).tolist(),
    }


def check_date_validity(df: pd.DataFrame, col: str) -> dict:
    values = present_values(df[col]).astype(str)
    values = values[values.str.strip() != ""]
    parsed = pd.to_datetime(values, errors="coerce", format="mixed", utc=True)
    invalid_mask = parsed.isna()
    invalid = values[invalid_mask]
    return {
        "check": "invalid_date", "column": col, "count": int(invalid_mask.sum()),
        "pct": round(100 * invalid_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": invalid.index.tolist(), "examples": invalid.head(3).tolist(),
    }


def check_phone_validity(df: pd.DataFrame, col: str) -> dict:
    values = present_values(df[col]).astype(str)
    values = values[values.str.strip() != ""]
    digit_counts = values.str.replace(r'\D', '', regex=True).str.len()
    # Optional initial plus/prefix, then an optional parenthesized digit group
    # followed by digits. Single spaces, dots and hyphens separate digit groups;
    # parentheses themselves can delimit a group without an extra separator.
    # No country-specific group lengths are assumed.
    phone_structure = (
        r'\+?(?:\d+(?:[ .-]\d+)*'
        r'|(?:\d+[ .-]?)?\(\d+\)[ .-]?\d+(?:[ .-]\d+)*)'
    )
    invalid_mask = (digit_counts < 7) | (digit_counts > 15) | ~values.str.fullmatch(phone_structure)
    invalid = values[invalid_mask]
    return {
        "check": "invalid_phone", "column": col, "count": int(invalid_mask.sum()),
        "pct": round(100 * invalid_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": invalid.index.tolist(), "examples": invalid.head(3).tolist(),
    }


def check_currency_validity(df: pd.DataFrame, col: str) -> dict:
    values = present_values(df[col]).astype(str)
    values = values[values.str.strip() != ""]
    invalid_mask = ~values.str.match(CURRENCY_PATTERN)
    invalid = values[invalid_mask]
    return {
        "check": "invalid_currency", "column": col, "count": int(invalid_mask.sum()),
        "pct": round(100 * invalid_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": invalid.index.tolist(), "examples": invalid.head(3).tolist(),
    }


# ============== NEW ENHANCED CHECKS ==============

def check_numeric_bounds(df: pd.DataFrame, col: str) -> dict:
    """Flag parsing/finiteness failures; headers cannot establish valid bounds."""
    values = present_values(df[col])
    # Float64 overflow/rounding is a representation limit, not proof that a
    # finite source number is invalid. Statistical profiling remains bounded
    # by floating-point arithmetic and reports that limitation separately.
    invalid_mask = values.map(lambda value: decimal_number(value) is None)
    invalid = values[invalid_mask]
    return {
        "check": "invalid_numeric", "column": col, "count": int(invalid_mask.sum()),
        "pct": round(100 * invalid_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": invalid.index.tolist(), "examples": invalid.head(3).astype(str).tolist(),
    }


def check_text_quality(df: pd.DataFrame, col: str) -> dict:
    """Flag control characters without imposing an unsupported text schema."""
    values = present_values(df[col]).astype(str)
    if values.empty:
        return {"check": "invalid_text", "column": col, "count": 0, "pct": 0, "row_indices": [], "examples": []}

    # Without a schema, length, punctuation, single letters and Unicode are valid.
    # Only embedded non-whitespace control characters are inherently suspicious.
    invalid_mask = values.str.contains(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", regex=True)
    invalid = values[invalid_mask]

    return {
        "check": "invalid_text",
        "column": col,
        "count": int(invalid_mask.sum()),
        "pct": round(100 * invalid_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": invalid.index.tolist(),
        "examples": invalid.head(3).tolist(),
    }


def check_categorical_consistency(df: pd.DataFrame, col: str) -> dict:
    """
    Find rare edit-distance spelling candidates, never established invalidity.
    Case/whitespace variants belong to the separate representation check.
    """
    values = present_values(df[col]).astype(str)
    values = values[values.str.strip() != ""]
    if len(values) < 3:
        return {"check": "invalid_categorical", "column": col, "count": 0, "pct": 0, "row_indices": [], "examples": []}

    # Get value counts
    value_counts = values.value_counts()
    total = len(values)

    # Flag values that appear only once and represent less than 5% of total
    rare_mask = values.map(value_counts) <= 1
    rare_pct = (rare_mask.sum() / total) * 100 if total else 0

    # Only flag if rare values are less than 5% of total (avoid flagging high-cardinality columns)
    if rare_pct > 5:
        rare_mask = pd.Series(False, index=values.index)

    common = [str(value).strip().casefold() for value, count in value_counts.items() if count > 1]
    def likely_typo(value):
        normalised = str(value).strip().casefold()
        return len(normalised) >= 4 and normalised not in common and bool(get_close_matches(normalised, common, n=1, cutoff=0.85))
    invalid_mask = rare_mask & values.map(likely_typo)
    invalid = values[invalid_mask]

    return {
        "check": "invalid_categorical",
        "review_only": True,
        "column": col,
        "count": int(invalid_mask.sum()),
        "pct": round(100 * invalid_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": invalid.index.tolist(),
        "examples": invalid.head(3).tolist(),
    }


# ============== VALIDITY CHECKS DICTIONARY ==============

VALIDITY_CHECKS = {
    "email": check_email_validity,
    "date": check_date_validity,
    "phone": check_phone_validity,
    "currency": check_currency_validity,
    "numeric": check_numeric_bounds,
    "text": check_text_quality,
    "categorical": check_categorical_consistency,
}


def run_validity_checks(df: pd.DataFrame, column_types: dict) -> list:
    issues = []
    for col, col_type in column_types.items():
        check_fn = VALIDITY_CHECKS.get(col_type)
        if check_fn:
            result = check_fn(df, col)
            if result["count"] > 0:
                issues.append(result)
    return issues
