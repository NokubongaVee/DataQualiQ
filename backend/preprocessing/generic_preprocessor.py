"""Explicit, auditable, stateless transformations. Defaults leave values intact.

No median/mode fitting, encoding, scaling or model training occurs here.
Row references are zero-based source positions, not potentially duplicated index labels.
"""
from dataclasses import dataclass, field
from copy import deepcopy
import numpy as np
import pandas as pd
from value_utils import missing_mask, decimal_number
from finding_categories import classify_findings, category_summary, ANALYTICAL


@dataclass(frozen=True)
class FieldPolicy:
    trim: bool = False
    case: str | None = None
    numeric: bool = False
    invalid: str = 'preserve'
    missing: str = 'preserve'
    fill_value: object = None
    reason: str = ''

    def __post_init__(self):
        if not isinstance(self.reason, str):
            raise ValueError('Transformation reason must be text.')
        if not isinstance(self.trim, bool) or not isinstance(self.numeric, bool):
            raise ValueError('Trim/numeric options must be booleans.')
        if self.case not in {None, 'lower', 'upper', 'casefold'}:
            raise ValueError('Case must be lower, upper, casefold or None.')
        if self.invalid not in {'preserve', 'mark_missing', 'reject'}:
            raise ValueError('Invalid values: preserve, mark_missing or reject.')
        if self.missing not in {'preserve', 'constant', 'reject'}:
            raise ValueError('Missing values: preserve, constant or reject. Learned imputation belongs to Phase 3.')
        if (self.trim or self.case or self.numeric or self.invalid != 'preserve' or self.missing != 'preserve') and not self.reason.strip():
            raise ValueError('Every enabled transformation requires an explicit reason.')
        if self.missing == 'constant' and (self.fill_value is None or missing_mask(pd.Series([self.fill_value])).iloc[0]):
            raise ValueError('Constant filling requires a non-missing explicit value.')
        if self.missing == 'constant' and not pd.api.types.is_scalar(self.fill_value):
            raise ValueError('Constant fill value must be scalar.')
        if self.numeric and self.missing == 'constant' and decimal_number(self.fill_value) is None:
            raise ValueError('Known numeric fields require a finite numeric fill value.')
        if self.numeric and self.case:
            raise ValueError('Numeric conversion and category case normalization cannot be combined.')


@dataclass(frozen=True)
class PreprocessingPolicy:
    fields: dict[str, FieldPolicy] = field(default_factory=dict)
    protected_fields: tuple[str, ...] = ()
    duplicate_policy: str = 'detect_only'
    allow_duplicate_removal: bool = False
    duplicate_reason: str = ''
    include_examples: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'fields', dict(self.fields))
        if not isinstance(self.allow_duplicate_removal, bool) or not isinstance(self.include_examples, bool):
            raise ValueError('Removal permission and example options must be booleans.')
        if not isinstance(self.duplicate_reason, str):
            raise ValueError('Duplicate provenance reason must be text.')
        if isinstance(self.protected_fields, str):
            raise ValueError('Protected fields must be a sequence of names.')
        object.__setattr__(self, 'protected_fields', tuple(self.protected_fields))
        if not all(isinstance(name, str) and name for name in self.protected_fields):
            raise ValueError('Protected fields must contain nonempty column names.')
        if self.duplicate_policy not in {'detect_only', 'remove_exact'}:
            raise ValueError('Duplicate policy must be detect_only or remove_exact.')
        if self.duplicate_policy == 'remove_exact' and (not self.allow_duplicate_removal or not self.duplicate_reason.strip()):
            raise ValueError('Exact-duplicate removal requires explicit permission in the policy and a reason.')
        if not all(isinstance(value, FieldPolicy) for value in self.fields.values()):
            raise ValueError('Policy fields must map to FieldPolicy objects.')


def preprocess_dataframe(df, policy=None, findings=None, validation_rules=None):
    policy = policy or PreprocessingPolicy()
    if not df.columns.is_unique:
        raise ValueError('Preprocessing requires unique column names.')
    protected = set(policy.protected_fields)
    validation_rules = validation_rules or {}
    unknown = set(policy.fields) - set(df.columns)
    if unknown:
        raise ValueError(f'Policy references absent fields: {sorted(unknown)}')
    for name, plan in policy.fields.items():
        if name in protected and plan != FieldPolicy():
            raise ValueError(f'Protected field {name!r} cannot be transformed or imputed.')
        if plan.invalid != 'preserve' and not plan.numeric and name not in validation_rules:
            raise ValueError('Invalid-value correction requires an explicit numeric or domain rule.')
        if name in validation_rules:
            if plan.missing == 'constant' and not validation_rules[name](plan.fill_value):
                raise ValueError(f'Fill value violates schema for {name!r}.')
    original = df.copy(deep=True).reset_index(drop=True)
    processed = original.copy(deep=True)
    classified = classify_findings(findings or ())
    operations, rejected, affected_rows, affected_columns = [], set(), set(), set()
    skipped_operations = []

    def record(operation, column, rows, reason, category, before=None, after=None):
        rows = sorted(set(int(i) for i in rows))
        if not rows:
            return
        item = {'operation': operation, 'column': column, 'rows_affected': len(rows),
                'source_row_positions': rows, 'reason': reason, 'category': category,
                'rule': operation, 'safe': True}
        if policy.include_examples and column is not None and before is not None:
            def display(value):
                return None if pd.isna(value) else str(value)[:120]
            item['examples'] = [{'source_row_position': i, 'before': display(before.iloc[i]),
                                 'after': display(after.iloc[i]) if after is not None else None} for i in rows[:3]]
        operations.append(item)
        affected_rows.update(rows)
        if column is None:
            affected_columns.update(processed.columns)
        else:
            affected_columns.add(column)

    for name, plan in policy.fields.items():
        if name in protected:
            continue
        for operation, enabled in [('trim_whitespace', plan.trim), ('normalize_case', plan.case is not None)]:
            if not enabled:
                continue
            before = processed[name].copy()
            after = before.map(lambda value: (value.strip() if operation == 'trim_whitespace' else getattr(value, plan.case)())
                               if isinstance(value, str) else value)
            changed = [i for i in range(len(df)) if isinstance(before.iloc[i], str) and before.iloc[i] != after.iloc[i]]
            if changed:
                processed[name] = after
            record(operation, name, changed, plan.reason, 'quality_issue', before, after)

        invalid_rows = set()
        # Domain-proven invalidity is evaluated on the current copy, independently
        # of labels and of any statistical anomaly finding.
        if name in validation_rules:
            present = ~missing_mask(processed[name])
            invalid_rows.update(i for i in range(len(df)) if present.iloc[i] and not validation_rules[name](processed[name].iloc[i]))
        if plan.numeric:
            before = processed[name].copy()
            present = ~missing_mask(before)
            numeric = pd.to_numeric(before.where(present), errors='coerce')
            finite = pd.Series(np.isfinite(numeric.fillna(np.nan).astype(float)), index=numeric.index)
            invalid_rows.update(i for i in before.index[present] if decimal_number(before.iloc[i]) is None)
            good = present & finite
            # Preserve exact integers and avoid silent rounding of large Decimal
            # values into float64. Only lossless finite conversions are permitted.
            from decimal import Decimal
            lossless = good.copy()
            for i in numeric.index[good]:
                lossless.iloc[i] = Decimal(str(numeric.iloc[i])) == Decimal(str(before.iloc[i]).strip())
            # Precision-limited but structurally valid values stay raw. They
            # must not become data errors merely because float64 is inadequate.
            skipped = [int(i) for i in before.index[present & ~lossless] if decimal_number(before.iloc[i]) is not None]
            if skipped:
                skipped_operations.append({'operation': 'parse_numeric', 'column': name,
                    'source_row_positions': skipped, 'rows_affected': len(skipped),
                    'reason': 'Structurally finite values retained raw because lossless conversion is unavailable.'})
            after = before.copy() if pd.api.types.is_numeric_dtype(before.dtype) else before.astype(object).copy()
            if not pd.api.types.is_numeric_dtype(before.dtype):
                after.loc[lossless] = numeric.loc[lossless].astype(object)
            processed[name] = after
            changed = [i for i in numeric.index[lossless] if isinstance(before.iloc[i], str)]
            record('parse_numeric', name, changed, plan.reason + ' Lossless finite conversion only.', 'quality_issue', before, after)
        if invalid_rows and plan.invalid == 'mark_missing':
            before = processed[name].copy()
            processed[name] = processed[name].astype(object)
            processed.loc[sorted(invalid_rows), name] = pd.NA
            record('mark_invalid_missing', name, invalid_rows, plan.reason, 'data_error', before, processed[name])
        elif invalid_rows and plan.invalid == 'reject':
            rejected.update(invalid_rows)
            record('reject_invalid_rows', name, invalid_rows, plan.reason, 'data_error', processed[name])
        elif invalid_rows:
            skipped_operations.append({'operation': 'correct_invalid_values', 'column': name,
                'source_row_positions': sorted(invalid_rows), 'rows_affected': len(invalid_rows),
                'reason': 'Invalid-value policy preserves source values for review.'})

        missing = missing_mask(processed[name])
        if plan.missing == 'constant':
            before = processed[name].copy()
            processed[name] = processed[name].astype(object)
            processed.loc[missing, name] = plan.fill_value
            record('fill_explicit_constant', name, processed.index[missing], plan.reason, 'quality_issue', before, processed[name])
        elif plan.missing == 'reject':
            rows = processed.index[missing].tolist()
            rejected.update(rows)
            record('reject_missing_rows', name, rows, plan.reason, 'quality_issue', processed[name])

    # Exactness refers to raw rows, never rows made equal by normalization.
    duplicate_rows = original.index[original.duplicated(keep='first')].tolist()
    if policy.duplicate_policy == 'remove_exact':
        rejected.update(duplicate_rows)
        record('remove_exact_duplicates', None, duplicate_rows, policy.duplicate_reason, 'quality_issue')
    kept = [i for i in processed.index if i not in rejected]
    output = processed.loc[kept].copy()
    output.index = df.index.take(kept)
    for name in protected & set(df.columns):
        pd.testing.assert_series_equal(output[name], df[name].iloc[kept], check_names=True)

    # Cell-level status makes partial correction/preservation explicit.
    statuses = []
    for finding in classified:
        name = finding.get('column')
        corrected, unchanged, excluded, numerically_preserved = [], [], [], []
        source_values = original[name].array if name in original and name in affected_columns else None
        processed_values = processed[name].array if source_values is not None else None
        for i in finding.get('row_indices', []):
            i = int(i)
            if not 0 <= i < len(df):
                raise ValueError('Finding refers to a row outside the supplied DataFrame.')
            if i in rejected:
                excluded.append(i)
            elif source_values is None:
                unchanged.append(i)
            else:
                before, after = source_values[i], processed_values[i]
                same = (pd.isna(before) and pd.isna(after)) or (not pd.isna(before) and not pd.isna(after) and before == after)
                (unchanged if same else corrected).append(i)
                if not same and finding['category'] == ANALYTICAL:
                    a, b = decimal_number(before), decimal_number(after)
                    if a is not None and b is not None and a == b:
                        numerically_preserved.append(i)
        statuses.append({'check': finding['check'], 'column': name, 'category': finding['category'],
                         'unchanged_rows': unchanged, 'changed_rows': corrected, 'excluded_rows': excluded,
                         'numerically_preserved_rows': numerically_preserved})
    report = {'input_rows': len(df), 'output_rows': len(output),
              'assessment_findings_supplied': findings is not None,
              'finding_summary': category_summary(classified), 'detected_findings': deepcopy(classified),
              'automatic_corrections': operations, 'finding_statuses': statuses,
              'skipped_operations': skipped_operations,
              'unchanged_findings': [item for item in statuses if item['unchanged_rows']],
              'preserved_anomalies': [item for item in statuses if item['category'] == ANALYTICAL and (item['unchanged_rows'] or item['numerically_preserved_rows'])],
              'rows_affected': len(affected_rows), 'source_rows_affected': sorted(affected_rows),
              'columns_affected': sorted(affected_columns), 'excluded_source_rows': sorted(rejected),
              'output_source_row_positions': kept,
              'duplicates': {'policy': policy.duplicate_policy, 'detected_excess_rows': len(duplicate_rows),
                             'source_row_positions': duplicate_rows},
              'protected_fields': sorted(protected), 'learned_parameters': None,
              'limitations': ['No fitted imputers, encoders or scalers. Fit these on training data only in Phase 3.',
                             'Source rows and statistical extremes are preserved by default.',
                             'Finding counts can overlap; occurrence totals are not distinct affected rows.']}
    return output, report
