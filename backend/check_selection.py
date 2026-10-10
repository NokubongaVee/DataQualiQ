"""Explainable routing to existing detectors; selection is independent of domain."""
from generic_checks import (check_missing, check_duplicate_rows, check_categorical_format,
                            check_numeric_format_consistency, check_date_format_consistency)
from validity_checks import VALIDITY_CHECKS, check_text_quality
from anomaly_detection import check_numeric_outliers
from value_utils import present_values
from profiling import shape
import pandas as pd
import math


def representable_fences(numeric):
    q1, q3 = numeric.get('q1'), numeric.get('q3')
    return q1 is not None and q3 is not None and all(math.isfinite(v) for v in
        (q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)))


def select_checks(profile: dict) -> dict:
    dtype, role = profile['type'], profile['role']
    full = profile['measurements']['full']
    numeric = full['numeric'] or {}
    specs = {
        'missing': (True, 'Missingness is observable for every field.'),
        'control_characters': (True, 'Non-whitespace control characters are structural observations.'),
        'validity': (dtype in VALIDITY_CHECKS and dtype != 'text', f'Observed representation is {dtype}.'),
        'category_format': (dtype == 'categorical', 'Repeated labels can be compared without assuming their meaning.'),
        'numeric_format': (dtype in {'numeric', 'currency'}, 'Values support a numeric representation.'),
        'date_format': (dtype == 'date', 'Parseable dates can be compared for representation and ambiguity.'),
        'outlier': (dtype == 'numeric' and role != 'identifier' and numeric.get('finite_count', 0) >= 5
                    and numeric.get('distinct_count', 0) > 1
                    and representable_fences(numeric)
                    and not (numeric.get('min') == 0 and numeric.get('max') == 1),
                    'Requires five finite numbers, representable IQR fences, variation, and no identifier or binary-indicator interpretation.'),
        'identifier_pattern': (role == 'identifier' and full['present_count'] >= 20,
                               'Candidate identifiers need sufficient support for a dominant shape.'),
        'repeated_identifier': (role == 'identifier', 'Compact identifiers may repeat; repetition does not establish an error.'),
        'header_conflict': (bool(profile['contradictions']), 'Header interpretation contradicts observed value patterns.'),
        'percentage': (dtype == 'percentage', 'Percent symbols support syntax checking, but do not establish a 0–100 business bound.'),
    }
    return {key: {'selected': bool(selected), 'reason': reason if selected else 'Skipped: ' + reason}
            for key, (selected, reason) in specs.items()}


def finding(check, col, rows, denominator, **extra):
    rows = sorted(int(i) for i in rows)
    return {'check': check, 'column': col, 'count': len(rows),
            'pct': round(100 * len(rows) / max(denominator, 1), 1),
            'row_indices': rows, 'denominator': int(denominator), **extra}


def run_selected_checks(df, profiles):
    issues = [check_duplicate_rows(df)]
    functions = {'missing': check_missing, 'control_characters': check_text_quality,
                 'category_format': check_categorical_format, 'numeric_format': check_numeric_format_consistency,
                 'date_format': check_date_format_consistency, 'outlier': check_numeric_outliers}
    for col, profile in profiles.items():
        plan = select_checks(profile)
        if profile.get('schema_rule'):
            for key in ('validity', 'control_characters'):
                plan[key] = {'selected': False, 'reason': 'Skipped: explicit schema validates this field without duplicating generic syntax penalties.'}
        if col in profile.get('protected_fields', ()):
            for key in plan:
                if key != 'missing':
                    plan[key] = {'selected': False, 'reason': 'Skipped: protected target/leakage field is not used to infer feature validity.'}
        profile['checks'] = plan
        for key, entry in plan.items():
            if not entry['selected']:
                continue
            fn = VALIDITY_CHECKS[profile['type']] if key == 'validity' else functions.get(key)
            if fn:
                result = fn(df, col)
                result['selection_reason'] = entry['reason']
                issues.append(result)
        values = present_values(df[col]).astype(str)
        if plan['header_conflict']['selected']:
            issues.append(finding('header_conflict', col, values.index, len(values),
                                  observations=profile['contradictions'], review_only=True))
        if plan['identifier_pattern']['selected']:
            shapes = values.map(shape)
            counts = shapes.value_counts()
            if len(counts) > 1 and counts.iloc[0] / len(values) >= .9:
                issues.append(finding('pattern_deviation', col, shapes[shapes != counts.index[0]].index,
                                      len(values), observed_pattern=counts.index[0],
                                      pattern_support=int(counts.iloc[0]), review_only=True))
        if plan['percentage']['selected']:
            invalid = ~values.str.fullmatch(r'[+-]?\d+(?:\.\d+)?%')
            issues.append(finding('invalid_percentage', col, values[invalid].index, len(values)))
        if plan['date_format']['selected']:
            parts = values.str.extract(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:$|\s)')
            a, b = pd.to_numeric(parts[0], errors='coerce'), pd.to_numeric(parts[1], errors='coerce')
            ambiguous = a.between(1, 12) & b.between(1, 12) & a.ne(b)
            issues.append(finding('ambiguous_date', col, values[ambiguous].index, len(values),
                                  observed_pattern='Both day-first and month-first interpretations are possible.', review_only=True))
    return [i for i in issues if i['count'] > 0]
