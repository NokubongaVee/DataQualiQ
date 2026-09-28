"""Measured evidence. Expensive string/date observations use a bounded sample.

Confidence elsewhere is heuristic support, never a calibrated probability.
Raw CSV values are never rewritten by profiling.
"""
import re
import numpy as np
import pandas as pd
from value_utils import present_values, missing_mask

SAMPLE_LIMIT = 1000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PHONE_PATTERN = re.compile(r"\+?(?:\d+(?:[ .-]\d+)*|(?:\d+[ .-]?)?\(\d+\)[ .-]?\d+(?:[ .-]\d+)*)")
CURRENCY_PATTERN = re.compile(r"^[+-]?[R$€£]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?$")


def finite_float(value):
    return float(value) if pd.notna(value) and np.isfinite(value) else None


def shape(value: str) -> str:
    """Unicode-aware runs; lengths are measured separately."""
    return re.sub(r"(.)\1+", r"\1", ''.join('A' if c.isalpha() else '9' if c.isdigit() else c for c in value))[:80]


def frequencies(values, limit=8):
    counts = values.value_counts()
    return [{"value": str(v)[:120], "count": int(n)} for v, n in counts.head(limit).items()]


@np.errstate(over='ignore', invalid='ignore')
def profile_column(series: pd.Series) -> dict:
    present = present_values(series).astype(str)
    count = len(present)
    sample = present.sample(n=min(count, SAMPLE_LIMIT), random_state=0)
    numeric = pd.to_numeric(present, errors='coerce')
    finite = numeric[np.isfinite(numeric)].astype(float)
    lengths = sample.str.len()
    # Numeric strings must not become nanosecond timestamps or year-only dates.
    date_shape = sample.str.contains(r'\d[-/.]\d|[A-Za-z]{3,}\s+\d|\d\s+[A-Za-z]{3,}', regex=True)
    dates = pd.to_datetime(sample.where(date_shape), errors='coerce', format='mixed', utc=True)
    phone = sample.str.fullmatch(PHONE_PATTERN) & sample.str.replace(r'\D', '', regex=True).str.len().between(7, 15)
    def ratio(mask):
        return float(mask.mean()) if len(mask) else 0.0
    counts = present.value_counts()
    n = len(series)
    stats = None
    if len(finite):
        stats = {k: finite_float(v) for k, v in {
            'min': finite.min(), 'max': finite.max(), 'mean': finite.mean(),
            'median': finite.median(), 'std': finite.std(ddof=0),
            'q1': finite.quantile(.25), 'q3': finite.quantile(.75),
            'skew': finite.skew() if len(finite) >= 3 else None,
        }.items()}
        stats.update(finite_count=len(finite), integer_ratio=ratio(finite.eq(finite.round())),
                     distinct_count=int(finite.nunique()),
                     arithmetic_limited=any(stats[k] is None for k in ('mean', 'std', 'q1', 'q3')))
    return {
        'full': {'row_count': n, 'present_count': count,
                 'missing_count': int(missing_mask(series).sum()),
                 'missing_percentage': round(100 * (n-count) / max(n, 1), 2),
                 'blank_count': int(series.astype('string').str.strip().eq('').sum()),
                 'unique_count': int(present.nunique()),
                 'uniqueness': present.nunique() / max(count, 1),
                 'repeated_occurrences': int(counts[counts > 1].sum()),
                 'excess_repetitions': int(count - present.nunique()),
                 'numeric_parse_ratio': ratio(numeric.notna()),
                 'finite_numeric_ratio': len(finite) / max(count, 1),
                 'common_values': frequencies(present),
                 'frequency_summary': {'singleton_values': int((counts == 1).sum()),
                                       'repeated_values': int((counts > 1).sum())},
                 'numeric': stats},
        'sample': {'size': len(sample), 'population': count, 'limit': SAMPLE_LIMIT,
                   'method': 'deterministic random sample, seed 0',
                   'email_ratio': ratio(sample.str.fullmatch(EMAIL_PATTERN)),
                   'phone_ratio': ratio(phone & dates.isna()),
                   'formatted_phone_ratio': ratio(phone & dates.isna() & sample.str.contains(r'[+() .-]', regex=True)),
                   'currency_ratio': ratio(sample.str.fullmatch(CURRENCY_PATTERN)),
                   'currency_symbol_ratio': ratio(sample.str.contains(r'[R$€£]', regex=True)),
                   'percentage_ratio': ratio(sample.str.fullmatch(r'[+-]?\d+(?:\.\d+)?%')),
                   'date_parse_ratio': ratio(dates.notna()), 'date_shape_ratio': ratio(date_shape),
                   'date_range': {'min': str(dates.min()) if dates.notna().any() else None,
                                  'max': str(dates.max()) if dates.notna().any() else None},
                   'code_ratio': ratio(sample.str.fullmatch(r'(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9_-]{2,64}')),
                   'leading_zero_ratio': ratio(sample.str.fullmatch(r'0\d+')),
                   'prose_ratio': ratio(sample.str.split().str.len().ge(4)),
                   'length': {'min': int(lengths.min()) if len(lengths) else 0,
                              'max': int(lengths.max()) if len(lengths) else 0,
                              'median': finite_float(lengths.median()) if len(lengths) else None},
                   'patterns': frequencies(sample.map(shape)),
                   'examples': sample.head(3).str.slice(0, 120).tolist()},
    }
