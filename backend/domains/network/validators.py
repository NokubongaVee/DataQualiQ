"""Read-only structural network validation, independent of target labels."""
from ipaddress import ip_address
import re
from value_utils import missing_mask, decimal_number


def valid_value(value, rule):
    text = str(value).strip()
    if rule.kind in {'number', 'nonnegative', 'count', 'port', 'binary'}:
        number = decimal_number(value)
        if number is None:
            return False
        if rule.kind == 'number':
            return True
        if rule.kind == 'nonnegative':
            return number >= 0
        if rule.kind == 'count':
            return number >= 0 and number == number.to_integral_value()
        if rule.kind == 'port':
            return 0 <= number <= 65535 and number == number.to_integral_value()
        return number in {0, 1}
    if rule.kind == 'ip':
        try:
            ip_address(text)
            return True
        except ValueError:
            return False
    if re.search(r'[\x00-\x1f\x7f]', text):
        return False
    if rule.allowed_values:
        transform = (lambda x: x) if rule.case_sensitive else str.casefold
        return transform(text) in {transform(v) for v in rule.allowed_values}
    if rule.kind == 'protocol':
        if re.fullmatch(r'\d+', text):
            return 0 <= int(text) <= 255
        # Registered names may start with digits and contain dots, plus signs
        # or slashes (3PC, AX.25, TP++, A/N). Validate token structure rather
        # than assuming a dataset-specific vocabulary or letters-only names.
        return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+/-]*', text))
    return bool(text)  # Category spelling/rarity alone never establishes invalidity.


def validate_network(df, schema):
    findings, warnings = [], []
    for name, rule in schema.fields.items():
        if name not in df:
            warnings.append({'kind': 'missing_schema_field', 'column': name,
                             'required': rule.required, 'message': f'Configured field {name!r} is absent.'})
            if rule.required:
                findings.append({'check': 'network_missing_field', 'column': name,
                    'count': len(df), 'pct': 100.0, 'denominator': len(df),
                    'row_indices': list(range(len(df))), 'category': 'data_error',
                    'reason': 'A field required by the supplied schema is absent.', 'source': 'network_schema', 'score_weight': 8})
            continue
        missing = missing_mask(df[name])
        mask = missing.to_numpy(dtype=bool)
        invalid = [position for position, value in enumerate(df[name].array)
                   if not mask[position] and not valid_value(value, rule)]
        if invalid:
            findings.append({'check': 'network_invalid_' + rule.kind, 'column': name,
                'count': len(invalid), 'pct': round(100 * len(invalid) / max(int((~missing).sum()), 1), 1),
                'denominator': int((~missing).sum()), 'row_indices': invalid,
                'category': 'data_error', 'reason': f'Violates explicit {rule.kind} structural/domain rule.',
                'source': 'network_schema', 'schema': schema.name, 'score_weight': 8,
                'examples': [str(df[name].iloc[i])[:120] for i in invalid[:3]]})
    return findings, warnings
