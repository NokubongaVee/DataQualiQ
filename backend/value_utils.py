"""Shared missing-value semantics for profiling and checks."""
import pandas as pd
from decimal import Decimal, InvalidOperation

MISSING_VALUE_TOKENS = frozenset({'na', 'n/a', 'null', 'nan', 'none'})


def missing_mask(values: pd.Series) -> pd.Series:
    normalised = values.astype('string').str.strip().str.lower()
    return (values.isna() | normalised.eq('') | normalised.isin(MISSING_VALUE_TOKENS)).fillna(True)


def present_values(values: pd.Series) -> pd.Series:
    return values[~missing_mask(values)]


def decimal_number(value):
    """Parse a finite decimal without rounding through binary floating point."""
    try:
        number = Decimal(str(value).strip())
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None
