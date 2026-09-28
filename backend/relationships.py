"""Bounded within-file relationships. No inferred relationship is a business rule."""
from itertools import combinations
import pandas as pd
from value_utils import missing_mask, present_values
from check_selection import finding

MAX_COLUMNS = 24
MAX_ROWS = 20000


def analyse_relationships(df, profiles):
    findings, relationships = [], []
    # Identifier repetition is a full-column observation. Associated-field
    # comparisons are bounded; make partial coverage explicit.
    associated = sorted(df.columns)[:MAX_COLUMNS]
    for col, profile in profiles.items():
        if profile['role'] != 'identifier':
            continue
        values = present_values(df[col]).astype(str)
        repeated = values[values.duplicated(keep=False)]
        if repeated.empty:
            continue
        other = [c for c in associated if c != col]
        rows = repeated.index
        examined = rows[:MAX_ROWS]
        frame = df.loc[examined, other].copy()
        variation = frame.groupby(values.loc[examined], sort=False).nunique(dropna=False)
        conflicting_cols = variation.columns[(variation > 1).any()].tolist()
        conflict_keys = variation.index[(variation > 1).any(axis=1)]
        conflict_rows = repeated[repeated.isin(conflict_keys)].index.tolist()
        # Exact rows and repeated keys are separate observations, without
        # multiplying the legacy quality-score penalty for the same cells.
        findings.append(finding('repeated_identifier', col, rows, len(values), review_only=True,
            relationship={'kind': 'repeated_identifier', 'distinct_repeated_values': int(repeated.nunique()),
                          'conflicting_columns': conflicting_cols, 'conflicting_row_indices': conflict_rows,
                          'associated_columns_checked': other, 'associated_rows_checked': len(examined),
                          'complete': len(rows) <= MAX_ROWS and len(df.columns) <= MAX_COLUMNS,
                          'examples': repeated.drop_duplicates().head(3).tolist()}))
    # Pair exploration is bounded and deterministic. Findings only refer to
    # examined rows; unsupported unique determinants are excluded entirely.
    subset = df if len(df) <= MAX_ROWS else df.sample(MAX_ROWS, random_state=0).sort_index()
    columns = sorted(df.columns)[:MAX_COLUMNS]
    masks = {col: missing_mask(subset[col]) for col in columns}
    for left, right in combinations(columns, 2):
        a, b = masks[left], masks[right]
        union, overlap = int((a | b).sum()), int((a & b).sum())
        if overlap >= 5 and union and overlap / union >= .8 and not a.all() and not b.all():
            relationships.append({'kind': 'co_missingness', 'columns': [left, right],
                                  'overlap_count': overlap, 'union_count': union,
                                  'jaccard': round(overlap / union, 3), 'rows_examined': len(subset)})
    categories = [c for c in columns if profiles[c]['type'] == 'categorical'
                  and profiles[c]['measurements']['full']['unique_count'] >= 2]
    for target in columns:
        missing = masks[target]
        if not missing.any():
            continue
        for group_col in categories:
            if group_col == target:
                continue
            present = ~masks[group_col]
            grouped = pd.DataFrame({'group': subset.loc[present, group_col].astype(str),
                                    'missing': missing[present]})
            summary = grouped.groupby('group')['missing'].agg(['sum', 'count'])
            for label, row in summary.iterrows():
                outside_n = len(subset) - int(row['count'])
                outside_missing = int(missing.sum()) - int(row['sum'])
                rate = row['sum'] / row['count']
                outside_rate = outside_missing / max(outside_n, 1)
                if row['count'] >= 5 and row['sum'] >= 3 and outside_n >= 5 and rate - outside_rate >= .25:
                    relationships.append({'kind': 'missing_concentration', 'column': target,
                        'group_column': group_col, 'group_value': str(label)[:120],
                        'missing_count': int(row['sum']), 'group_count': int(row['count']),
                        'group_rate': round(float(rate), 3), 'outside_rate': round(outside_rate, 3),
                        'rows_examined': len(subset)})
    for left, right in combinations(categories, 2):
        for determinant, dependent in ((left, right), (right, left)):
            both = ~(masks[determinant] | masks[dependent])
            pairs = subset.loc[both, [determinant, dependent]].astype(str)
            if len(pairs) < 20 or pairs[dependent].nunique() < 2:
                continue
            counts = pairs.groupby([determinant, dependent]).size()
            totals = counts.groupby(level=0).sum()
            # Every determinant group needs repeated support, never singleton keys.
            eligible = totals[totals >= 5].index
            if len(eligible) < 2:
                continue
            modes = {}
            for value in eligible:
                group = counts.loc[value]
                if group.max() / group.sum() >= .9:
                    modes[value] = group.idxmax()
            if len(set(modes.values())) < 2:
                continue
            eligible_pairs = pairs[pairs[determinant].isin(modes)]
            expected = eligible_pairs[determinant].map(modes)
            deviations = eligible_pairs[dependent] != expected
            if len(eligible_pairs) < 20 or deviations.mean() > .05:
                continue
            relation = {'kind': 'categorical_dependency', 'determinant': determinant,
                        'dependent': dependent, 'support': len(eligible_pairs),
                        'agreement': round(1 - float(deviations.mean()), 3),
                        'rows_examined': len(subset),
                        'mappings': [{'from': k[:120], 'to': v[:120]} for k, v in list(modes.items())[:8]]}
            relationships.append(relation)
            if deviations.any():
                findings.append(finding('relationship_deviation', dependent,
                    eligible_pairs[deviations].index, len(eligible_pairs),
                    review_only=True, relationship=relation))
    return findings, {'observations': relationships, 'coverage': {
        'rows_examined_for_pairs': len(subset), 'columns_examined_for_pairs': columns,
        'row_limit': MAX_ROWS, 'column_limit': MAX_COLUMNS,
        'sampled': len(subset) < len(df), 'columns_truncated': len(columns) < len(df.columns)},
        'limitations': ['Associations are descriptive, not causal or established business constraints.',
                       'Only supported categorical mappings, missingness and candidate identifiers are examined.']}
