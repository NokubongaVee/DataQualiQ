"""Training-fitted, schema-driven ML features, separate from read-only quality checks."""
from copy import deepcopy
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder

from domains.network import NetworkSchema
from domains.network.validators import valid_value
from preprocessing import PreprocessingPolicy, preprocess_network
from value_utils import missing_mask

NUMERIC_KINDS = frozenset({'number', 'nonnegative', 'count', 'port', 'binary'})
MISSING_CATEGORY = '__dataqualiq_missing__'


def prepare_supervised_dataset(frame, schema, target, policy=None, dataset='training'):
    """Apply existing safe policies, then exclude unusable targets with source provenance.

    Never modifies the source or guesses labels. This is separate from transform(),
    which accepts future uploads without target/identifier/leakage columns.
    """
    if target not in schema.target_fields or target not in frame:
        raise ValueError('A configured target column is required for supervised preparation.')
    rule = schema.fields.get(target)
    if rule is None or rule.kind != 'binary':
        raise ValueError('This workflow requires an explicitly binary target schema.')
    output, audit = preprocess_network(frame, schema, policy or PreprocessingPolicy())
    missing = missing_mask(output[target])
    numeric = pd.to_numeric(output[target].where(~missing), errors='coerce')
    invalid = ~missing & ~numeric.isin([0, 1])
    kept = ~(missing | invalid)
    source_positions = np.asarray(audit['output_source_row_positions'])
    target_audit = {
        'column': target, 'missing': int(missing.sum()), 'invalid': int(invalid.sum()),
        'excluded': int((~kept).sum()), 'imputed': 0,
        'missing_source_rows': source_positions[missing.to_numpy()].tolist(),
        'invalid_source_rows': source_positions[invalid.to_numpy()].tolist(),
        'expected_values': {'0': 'Normal', '1': 'Malicious / Attack'},
    }
    labels = numeric.loc[kept].astype('int8').copy()
    labels.name = target
    cleaned = output.loc[kept].copy(deep=True)
    # Small summary of existing audit; no duplicated row-level Phase 2 responses.
    report = {
        'dataset': dataset, 'original_rows': len(frame), 'final_rows': len(cleaned),
        'missing_values_detected': {name: int(missing_mask(frame[name]).sum()) for name in frame},
        'duplicate_policy': audit['duplicates']['policy'],
        'duplicates_detected': audit['duplicates']['detected_excess_rows'],
        'duplicates_removed': sum(item['rows_affected'] for item in audit['automatic_corrections'] if item['operation'] == 'remove_exact_duplicates'),
        'normalizations': audit['automatic_corrections'],
        'protected_fields': audit['protected_fields'], 'target_validation': target_audit,
        'retained_source_rows': source_positions[kept.to_numpy()].tolist(),
        'class_distribution': class_distribution(labels),
    }
    return cleaned, labels, report


def class_distribution(labels):
    total = len(labels)
    normal = int(labels.eq(0).sum())
    malicious = int(labels.eq(1).sum())
    return {'total_records': total, 'normal': normal, 'malicious': malicious,
            'normal_percent': round(100 * normal / total, 4) if total else 0,
            'malicious_percent': round(100 * malicious / total, 4) if total else 0}


class NetworkMLPreprocessor:
    """fit/transform contract with learned median and one-hot state.

    Fixed normalizations use Phase 2 policies. Only fit learns statistics/vocabulary.
    A sparse CSR matrix uses numeric features first, then one-hot features; the
    exact order is retained in feature_names_out_. Unknown categories are all-zero
    blocks and audited; missing categories have a distinct reserved indicator.
    """

    def __init__(self, schema, normalization_policy=None):
        self.schema = NetworkSchema.from_dict(deepcopy(schema.to_dict()))
        self.normalization_policy = deepcopy(normalization_policy or PreprocessingPolicy())
        if self.normalization_policy.duplicate_policy != 'detect_only':
            raise ValueError('Row removal belongs to supervised preparation, not feature transform.')
        for name, plan in self.normalization_policy.fields.items():
            if name in self.schema.protected_fields:
                raise ValueError('ML normalization cannot reference protected fields.')
            if plan.numeric or plan.invalid != 'preserve' or plan.missing != 'preserve':
                raise ValueError('ML normalization policies may only trim or normalize case.')
        self.fitted_ = False

    def _features(self, frame):
        if not frame.columns.is_unique:
            raise ValueError('Feature columns must be unique.')
        columns = self.schema.feature_columns(frame.columns)
        if not columns:
            raise ValueError('No predictive features are available.')
        unknown = set(columns) - set(self.schema.fields)
        if unknown:
            raise ValueError(f'Predictive fields need explicit schema types: {sorted(unknown)}')
        return columns

    def _prepare(self, frame):
        absent = set(self.feature_columns_) - set(frame.columns)
        if absent:
            raise ValueError(f'Required ML features are absent: {sorted(absent)}')
        # Project BEFORE normalization. Labels, identifiers and leakage fields
        # never enter either a fitted transformer or its learned statistics.
        features = frame.loc[:, self.feature_columns_].copy(deep=True)
        features, phase2_audit = preprocess_network(features, self.schema, self.normalization_policy)
        audit = {'rows': len(features), 'normalizations': phase2_audit['automatic_corrections'],
                 'missing_detected': {}, 'missing_handled': {}, 'unseen_categories': {}, 'missing_operations': []}
        numeric = pd.DataFrame(index=features.index)
        categorical = pd.DataFrame(index=features.index)
        for name in self.feature_columns_:
            values = features[name]
            missing = missing_mask(values)
            count = int(missing.sum())
            audit['missing_detected'][name] = count
            audit['missing_handled'][name] = count
            if count:
                audit['missing_operations'].append({'column': name, 'rows_affected': count,
                    'operation': 'training_median_imputation' if name in self.numeric_features_ else 'explicit_missing_category',
                    'source_row_positions': np.flatnonzero(missing.to_numpy()).tolist(),
                    'row_reference': 'positions within this supplied feature frame'})
            if name in self.numeric_features_:
                parsed = pd.to_numeric(values.where(~missing), errors='coerce').astype('float64')
                finite = np.isfinite(parsed.to_numpy())
                if bool((~missing.to_numpy() & ~finite).any()):
                    raise ValueError(f'Invalid or non-finite numeric feature {name!r}; review quality findings before ML preparation.')
                rule = self.schema.fields[name]
                # Independent structural validation, never IQR/capping or labels.
                if any(not valid_value(value, rule) for value in values.loc[~missing].array):
                    raise ValueError(f'Feature {name!r} violates its configured network rule.')
                numeric[name] = parsed
            else:
                present = values.loc[~missing].astype(str)
                if present.eq(MISSING_CATEGORY).any():
                    raise ValueError(f'Reserved missing category collides with a source value in {name!r}.')
                if any(not valid_value(value, self.schema.fields[name]) for value in present.array):
                    raise ValueError(f'Feature {name!r} violates its configured network rule.')
                categorical[name] = values.astype('string').where(~missing, MISSING_CATEGORY).astype(str)
        return numeric, categorical, audit

    def fit(self, training_data):
        # Refit starts a fresh state; failed fitting cannot leave an old model active.
        self.fitted_ = False
        self.feature_columns_ = self._features(training_data)
        self.numeric_features_ = [name for name in self.feature_columns_ if self.schema.fields[name].kind in NUMERIC_KINDS]
        self.categorical_features_ = [name for name in self.feature_columns_ if name not in self.numeric_features_]
        numeric, categorical, audit = self._prepare(training_data)
        if not len(training_data):
            raise ValueError('Cannot fit preprocessing on an empty training dataset.')
        all_missing = [name for name in numeric if numeric[name].isna().all()]
        if all_missing:
            raise ValueError(f'Training-only median unavailable for all-missing features: {all_missing}')
        self.imputer_ = SimpleImputer(strategy='median') if self.numeric_features_ else None
        if self.imputer_ is not None:
            self.imputer_.fit(numeric)
            # An even-sized median may overflow when averaging two individually
            # finite extremes. Keep those values; repair only the fitted statistic.
            for position, name in enumerate(self.numeric_features_):
                if not np.isfinite(self.imputer_.statistics_[position]):
                    ordered = np.sort(numeric[name].dropna().to_numpy())
                    middle = len(ordered) // 2
                    self.imputer_.statistics_[position] = ordered[middle] if len(ordered) % 2 else ordered[middle - 1] / 2 + ordered[middle] / 2
        self.encoder_ = None
        if self.categorical_features_:
            # Reserve missing indicator even if training has no missing categories.
            categories = [sorted(set(categorical[name]) | {MISSING_CATEGORY}) for name in self.categorical_features_]
            self.encoder_ = OneHotEncoder(categories=categories, handle_unknown='ignore', sparse_output=True, dtype=np.float64)
            self.encoder_.fit(categorical)
        self.feature_names_out_ = list(self.numeric_features_)
        if self.encoder_ is not None:
            self.feature_names_out_ += self.encoder_.get_feature_names_out(self.categorical_features_).tolist()
        if len(set(self.feature_names_out_)) != len(self.feature_names_out_):
            raise ValueError('Encoded feature names collide; revise schema column names.')
        self.medians_ = dict(zip(self.numeric_features_, self.imputer_.statistics_.tolist())) if self.imputer_ is not None else {}
        self.fit_audit_ = {**audit, 'fit_source': 'training_only', 'numeric_imputation': 'training median',
                           'categorical_imputation': MISSING_CATEGORY, 'encoder': 'OneHotEncoder(handle_unknown=ignore)',
                           'scaling': None, 'medians': dict(self.medians_)}
        self.fitted_ = True
        return self

    def transform(self, test_or_new_data):
        if not self.fitted_:
            raise ValueError('Fit the preprocessor on training data before transform.')
        if not test_or_new_data.columns.is_unique:
            raise ValueError('Feature columns must be unique.')
        numeric, categorical, audit = self._prepare(test_or_new_data)
        blocks = []
        if self.imputer_ is not None:
            blocks.append(sparse.csr_matrix(self.imputer_.transform(numeric)))
        if self.encoder_ is not None:
            for name, categories in zip(self.categorical_features_, self.encoder_.categories_):
                audit['unseen_categories'][name] = int((~categorical[name].isin(categories)).sum())
            blocks.append(self.encoder_.transform(categorical))
        matrix = sparse.hstack(blocks, format='csr')
        if not np.isfinite(matrix.data).all():
            raise ValueError('ML matrix contains non-finite values.')
        self.last_audit_ = {**audit, 'fit_source': 'existing_training_state', 'shape': list(matrix.shape),
                            'numeric_imputation': 'training median', 'categorical_imputation': MISSING_CATEGORY,
                            'encoder': 'OneHotEncoder(handle_unknown=ignore)', 'scaling': None}
        return matrix

    def fit_transform(self, training_data):
        return self.fit(training_data).transform(training_data)

    def get_feature_names_out(self):
        if not self.fitted_:
            raise ValueError('Preprocessor is not fitted.')
        return np.asarray(self.feature_names_out_, dtype=object)
