import re
import pandas as pd

from value_utils import missing_mask, present_values


def check_missing(df: pd.DataFrame, col: str) -> dict:
    total = len(df)
    values = df[col]
    is_missing = missing_mask(values)
    missing = int(is_missing.sum())
    pct = round(100 * missing / total, 1) if total else 0
    return {
        "check": "missing", "column": col, "count": int(missing), "pct": pct,
        "row_indices": df[is_missing].index.tolist(),
    }


def check_duplicate_rows(df: pd.DataFrame) -> dict:
    dup_mask = df.duplicated(keep="first")
    count = int(dup_mask.sum())
    return {
        "check": "duplicate", "column": None, "count": count,
        "pct": round(100 * count / len(df), 1) if len(df) else 0,
        "row_indices": df[dup_mask].index.tolist(),
    }


def check_categorical_format(df: pd.DataFrame, col: str) -> dict:
    """
    Flags category labels that are really the same value written
    differently — casing or whitespace variants
    (e.g. 'Poor', 'poor', ' Poor ' are all the same category).
    Does NOT flag short vs. long labels, since different valid
    categories naturally have different lengths.
    """
    values = present_values(df[col]).astype(str)
    values = values[values.str.strip() != ""]
    if values.empty:
        return {"check": "format", "column": col, "count": 0, "pct": 0, "row_indices": []}

    normalized = values.str.strip().str.lower()
    groups = pd.DataFrame({"raw": values, "norm": normalized})

    flagged_indices = []
    variants = []
    for _, group in groups.groupby("norm"):
        if group["raw"].nunique() > 1:
            majority_raw = group["raw"].value_counts().idxmax()
            flagged_indices.extend(group[group["raw"] != majority_raw].index.tolist())
            if len(variants) < 5:
                variants.append({'reference': str(majority_raw)[:120],
                                 'variants': group.loc[group['raw'] != majority_raw, 'raw'].drop_duplicates().head(3).str.slice(0, 120).tolist(),
                                 'reference_count': int((group['raw'] == majority_raw).sum())})

    return {
        "check": "format", "column": col, "count": len(flagged_indices),
        "pct": round(100 * len(flagged_indices) / len(values), 1) if len(values) else 0,
        "row_indices": flagged_indices,
        "format_evidence": variants,
        "denominator": len(values),
    }


def check_numeric_format_consistency(df: pd.DataFrame, col: str) -> dict:
    """
    For text columns that look like they're meant to be numbers
    (e.g. a price column stuck as text), flags rows written in a
    different style than the rest — malformed grouping, currency symbols, or
    stray whitespace mixed in inconsistently.
    """
    values = present_values(df[col]).astype(str)
    values = values[values.str.strip() != ""]
    if values.empty:
        return {"check": "format", "column": col, "count": 0, "pct": 0, "row_indices": []}

    has_digit = values.str.strip().str.match(r'^[+-]?[R$€£]?\s*\d[\d,.]*\s*$')
    if has_digit.mean() < 0.5:
        # Doesn't look numeric enough to check — leave free text alone.
        return {"check": "format", "column": col, "count": 0, "pct": 0, "row_indices": []}

    def style(v):
        has_symbol = bool(re.search(r'[R₹$€£]', v))
        # Proper thousands grouping is equivalent to ungrouped digits.
        # Keep unmatched comma notation visible to the consistency check.
        grouped_number = re.fullmatch(
            r'[+-]?[R₹$€£]?\s*\d{1,3}(?:,\d{3})+(?:\.\d+)?', v.strip()
        )
        has_comma = ',' in v and grouped_number is None
        has_space = v != v.strip()
        return (has_symbol, has_comma, has_space)

    styles = values[has_digit].apply(style)
    dominant_style = styles.value_counts().idxmax()
    inconsistent_mask = styles != dominant_style
    inconsistent = values.loc[styles.index[inconsistent_mask]]

    return {
        "check": "format", "column": col, "count": int(inconsistent_mask.sum()),
        "pct": round(100 * inconsistent_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": inconsistent.index.tolist(),
        "denominator": len(values),
        "observed_pattern": 'Reference numeric style: '
            + ('currency symbol present, ' if dominant_style[0] else 'no currency symbol, ')
            + ('unusual comma notation, ' if dominant_style[1] else 'conventional separators, ')
            + ('outer whitespace present.' if dominant_style[2] else 'no outer whitespace.'),
        "pattern_support": int((styles == dominant_style).sum()),
    }


def check_date_format_consistency(df: pd.DataFrame, col: str) -> dict:
    """Find mixed numeric date spellings among parseable, non-missing dates."""
    values = present_values(df[col]).astype(str)
    parsed = pd.to_datetime(values, errors="coerce", format="mixed", utc=True)
    values = values[parsed.notna()]
    styles = values.str.extract(r'^(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})', expand=False)
    # Day/month width varies naturally in unpadded date conventions. Preserve
    # separators and year width/position without guessing ambiguous day order.
    styles = styles.dropna().str.replace(
        r'\d+', lambda match: 'd' if len(match[0]) <= 2 else 'd' * len(match[0]),
        regex=True,
    )
    if styles.empty:
        return {"check": "format", "column": col, "count": 0, "pct": 0, "row_indices": []}
    dominant = styles.value_counts().idxmax()
    flagged = styles[styles != dominant]
    return {
        "check": "format", "column": col, "count": len(flagged),
        "pct": round(100 * len(flagged) / len(styles), 1),
        "row_indices": flagged.index.tolist(),
        "denominator": len(styles),
        "observed_pattern": f'Reference numeric date shape: {dominant}.',
        "pattern_support": int((styles == dominant).sum()),
    }


def run_generic_checks(df: pd.DataFrame, column_types: dict = None) -> list:
    issues = []
    column_types = column_types or {}
    for col in df.columns:
        issues.append(check_missing(df, col))

        col_type = column_types.get(col)
        if col_type == "categorical":
            # Check for the same category written differently
            # (casing, spacing, punctuation) — not shape/length.
            issues.append(check_categorical_format(df, col))
        elif col_type in {"text", "numeric", "currency"}:
            # Only worth checking if this "text" column actually
            # looks like it should be numbers (e.g. a price column
            # that didn't parse as numeric). Pure free text is skipped.
            issues.append(check_numeric_format_consistency(df, col))
        elif col_type == "date":
            issues.append(check_date_format_consistency(df, col))

    issues.append(check_duplicate_rows(df))
    return [i for i in issues if i["count"] > 0]
