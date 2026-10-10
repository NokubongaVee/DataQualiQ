"""Conservative inference from measured values and corroborating header hints."""
import re
import pandas as pd
from profiling import profile_column, EMAIL_PATTERN, PHONE_PATTERN, CURRENCY_PATTERN


def _normalise_label(value):
    """
    Convert column names into a consistent form.

    Examples:
        MonthlyPay   -> monthly_pay
        BusinessUnit -> business_unit
        DateJoined   -> date_joined
        ContractNo   -> contract_no
    """
    if value is None:
        return ""

    text = str(value).strip()

    # Split CamelCase / PascalCase.
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)

    # Convert separators to underscores.
    text = re.sub(r"[\s\-./]+", "_", text)

    # Remove unsupported characters.
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)

    # Remove repeated underscores.
    text = re.sub(r"_+", "_", text)

    return text.strip("_").lower()


def _tokenise_column_name(column_name):
    text = _normalise_label(column_name)

    if not text:
        return set()

    tokens = set()

    for piece in re.split(r"[_\s]+", text):
        cleaned = re.sub(r"[^a-z0-9]", "", piece)

        if cleaned:
            tokens.add(cleaned)

    return tokens


def _column_text_tokens(column_name):
    text = _normalise_label(column_name)

    return {
        part
        for part in re.split(r"[_\s]+", text)
        if part
    }


def infer_column_profile(series: pd.Series, column_name: str = '') -> dict:
    measured = profile_column(series)
    full, sample = measured['full'], measured['sample']
    tokens = _column_text_tokens(column_name or str(series.name or ''))
    n = full['present_count']
    candidates = []
    contradictions = []
    # One vocabulary match is one signal, regardless of how many synonyms match.
    hints = {
        'email': {'email', 'mail'}, 'phone': {'phone', 'mobile', 'telephone', 'tel', 'cell'},
        'date': {'date', 'datetime', 'timestamp'},
        'identifier': {'id', 'identifier', 'code', 'ref', 'reference', 'sku', 'no'},
        'monetary_value': {'price', 'cost', 'salary', 'wage', 'compensation', 'revenue', 'payment', 'fee'},
        'quantity': {'quantity', 'count', 'qty', 'units', 'stock'},
        'measurement': {'score', 'mark', 'measure', 'measurement', 'metric', 'height', 'weight'},
        'person_name': {'name'},
    }
    def add(role, strength, evidence, contradict=None):
        confidence = min(strength, .65 if n < 5 else .85 if n < 20 else .95)
        candidates.append({'role': role, 'confidence': round(confidence, 2),
                           'supporting_evidence': evidence, 'contradicting_evidence': contradict or []})
    for role in ('email', 'phone', 'date'):
        ratio = sample[{'email': 'email_ratio', 'phone': 'phone_ratio', 'date': 'date_parse_ratio'}[role]]
        named = bool(tokens & hints[role])
        value_support = ratio >= .7
        if role == 'phone':
            value_support = ratio >= .7 and (sample['formatted_phone_ratio'] >= .5 or named)
            if not named and full['numeric_parse_ratio'] >= .8:
                # Long decimal measurements also match phone digit/separator
                # syntax. A numeric representation alone is not contact data.
                value_support = False
        if value_support or (named and ratio >= .4):
            add(role, .7 + .2 * ratio, [f'{ratio:.1%} of sampled values match {role} syntax'] +
                ([f'header supports {role}'] if named else []))
        elif named and n:
            conflict = f'Header suggests {role}, but only {ratio:.1%} of sampled values match; numeric parsing succeeds for {full["numeric_parse_ratio"]:.1%} of present values.'
            contradictions.append(conflict)
            add(role, .25, [f'header suggests {role}'], [conflict])
    numeric = full['numeric_parse_ratio'] >= .8
    currency = sample['currency_ratio'] >= .7 and sample['currency_symbol_ratio'] > 0
    percent = sample['percentage_ratio'] >= .8
    if numeric:
        dtype = 'numeric'
    elif currency:
        dtype = 'currency'
    elif percent:
        dtype = 'percentage'
    elif n and full['unique_count'] < n and full['unique_count'] <= max(2, min(30, n * .5)) and sample['prose_ratio'] < .5:
        dtype = 'categorical'
    else:
        dtype = 'text' if n else 'unknown'
    supported = [c for c in candidates if not c['contradicting_evidence']]
    if supported:
        dtype = max(supported, key=lambda c: c['confidence'])['role']
    if currency:
        add('monetary_value', .8, ['currency symbols and numeric syntax occur together'])
    if percent:
        add('percentage', .8, ['values explicitly contain a percent symbol'])
    if dtype == 'numeric':
        for role in ('monetary_value', 'quantity', 'measurement'):
            if tokens & hints[role]:
                add(role, .65, ['numeric values corroborate a header hint; units and business purpose remain unverified'])
    # Unique prose and arbitrary names are not keys. Require a compact code
    # pattern, leading zeros, or a corroborated identifier header.
    compact = sample['prose_ratio'] < .2 and sample['length']['max'] <= 64
    key_shape = ((sample['code_ratio'] >= .8 and not numeric) or sample['leading_zero_ratio'] >= .8) and full['uniqueness'] >= .5
    named_key = bool(tokens & hints['identifier'])
    if n and compact and dtype not in {'email', 'phone', 'date', 'currency', 'percentage'} and (key_shape or named_key):
        add('identifier', .85 if named_key and sample['code_ratio'] >= .8 else .8 if key_shape else .65,
            [f'{full["uniqueness"]:.1%} distinct present values',
             'compact code pattern' if key_shape else 'identifier header and compact values; uniqueness is not a business constraint'])
    if dtype == 'text' and sample['prose_ratio'] >= .5:
        add('free_text', .85, ['most sampled values contain at least four words'])
    elif dtype == 'text' and 'name' in tokens and not tokens & {'product', 'course', 'company'}:
        add('person_name', .5, ['header suggests names; text alone cannot establish person identity'])
    elif dtype == 'categorical':
        add('category', .8, [f'{full["unique_count"]} distinct labels among {n} present values'])
    supported = sorted([c for c in candidates if not c['contradicting_evidence']], key=lambda c: -c['confidence'])
    best = supported[0] if supported else None
    # A numeric representation is useful even when its business meaning is unknown.
    role = best['role'] if best else 'unknown'
    evidence = best['supporting_evidence'] if best else ['No sufficiently supported semantic interpretation']
    return {'type': dtype, 'role': role, 'confidence': best['confidence'] if best else .2,
            'semantic_tags': [role] if role != 'unknown' else [], 'evidence': evidence,
            'alternatives': sorted(candidates, key=lambda c: -c['confidence']),
            'contradictions': contradictions, 'measurements': measured,
            'limitations': ['Semantic confidence is heuristic support, not a calibrated probability.',
                            'Sampled patterns may miss rare representations; business meaning and units are unverified.']
                + (['Some numeric summaries exceed floating-point arithmetic limits and are returned as null.']
                   if (full['numeric'] or {}).get('arithmetic_limited') else [])}


def infer_column_type(series: pd.Series) -> str:
    return infer_column_profile(series, str(series.name or ''))['type']


def infer_all_column_profiles(df: pd.DataFrame) -> dict:
    return {str(col): infer_column_profile(df[col], str(col)) for col in df.columns}


def infer_all_column_types(df: pd.DataFrame) -> dict:
    return {col: p['type'] for col, p in infer_all_column_profiles(df).items()}


