"""Link unchanged quality findings and saved-model inference by source position."""
from time import perf_counter
from copy import deepcopy
import numpy as np
import pandas as pd

from finding_categories import ERROR, QUALITY, ANALYTICAL
from pipeline import run_pipeline_from_dataframe
from preprocessing import preprocess_network
from value_utils import missing_mask
from .prediction import service, PredictionError, MAX_RECORD_RESULTS
from .preprocessing import MISSING_CATEGORY

POLICY_VERSION = 'input_integrity_v1'
MAX_FINDINGS_PER_RECORD = 10
MAX_PAGE_FINDINGS = 1000


def compact_finding(issue):
    return {'id': issue.get('id'), 'check': issue['check'],
            'column': str(issue['column'])[:120] if issue.get('column') is not None else None, 'category': issue['category'],
            'reason': str(issue.get('reason') or issue.get('selection_reason') or issue['check'].replace('_', ' '))[:240]}


def quality_overview(quality, row_count):
    """Compact measured detector counts; occurrences are not unique records."""
    groups = {name: {'finding_count': 0, 'occurrences': 0, 'affected_records': 0, 'by_column': []}
              for name in ['missing_values', 'duplicates', 'invalid_values', 'inconsistencies', 'analytical_anomalies']}
    masks = {name: np.zeros(row_count, dtype=bool) for name in groups}
    columns = {name: {} for name in groups}
    for issue in quality['issues']:
        if issue['check'] == 'missing':
            group = 'missing_values'
        elif issue['check'] == 'duplicate':
            group = 'duplicates'
        elif issue['category'] == ERROR:
            group = 'invalid_values'
        elif issue['category'] == ANALYTICAL:
            group = 'analytical_anomalies'
        else:
            group = 'inconsistencies'
        groups[group]['finding_count'] += 1
        groups[group]['occurrences'] += int(issue['count'])
        rows = np.asarray(issue.get('row_indices', []), dtype=np.int64)
        if rows.size:
            if (rows < 0).any() or (rows >= row_count).any():
                raise PredictionError('row_mapping_error', 'Quality findings contain incompatible source-row positions.', 500)
            masks[group][rows] = True
        column = issue.get('column')
        if column is not None:
            columns[group][column] = columns[group].get(column, 0) + int(issue['count'])
    for group, summary in groups.items():
        summary['affected_records'] = int(masks[group].sum())
        summary['by_column'] = [{'column': str(name)[:120], 'occurrences': count} for name, count in list(columns[group].items())[:100]]
        summary['columns_truncated'] = len(columns[group]) > 100
    groups['duplicates']['policy'] = 'preserved; counts exclude first occurrence under existing detector'
    groups['analytical_anomalies']['meaning'] = 'Analytical/statistical findings, not model-predicted attacks; occurrences can overlap across fields.'
    return {'score': quality['score'], 'grade': quality['grade'], 'label': quality.get('label'),
            **groups, 'finding_summary': quality['finding_summary'], 'score_policy': quality['score_policy']}


class CombinedAnalysisService:
    def __init__(self, predictor=None, *, duplicate_review=False):
        self.predictor = predictor or service
        self.duplicate_review = duplicate_review

    def analyze(self, dataframe, filename='uploaded.csv', *, offset=0, limit=100):
        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            raise PredictionError('invalid_input', 'A nonempty network DataFrame is required.')
        if not dataframe.columns.is_unique or not all(isinstance(c, str) for c in dataframe.columns):
            raise PredictionError('invalid_columns', 'Network column names must be unique strings.')
        if (type(offset) is not int or offset < 0 or type(limit) is not int or not 0 <= limit <= MAX_RECORD_RESULTS):
            raise PredictionError('invalid_pagination', 'Offset must be nonnegative; limit must be between 0 and 1000.')
        start = perf_counter()
        # Load through the Phase 7 lock; subsequent prediction calls take the
        # same lock. Only immutable schema/configuration is used outside it.
        with self.predictor._lock:
            model, preprocessor, metadata = self.predictor._load()
        required = metadata['features']['required_features']
        missing_columns = [name for name in required if name not in dataframe]
        if missing_columns:
            raise PredictionError('missing_features', 'Missing required network features: ' + ', '.join(missing_columns), fields=missing_columns)
        frame = dataframe.reset_index(drop=True)
        quality = run_pipeline_from_dataframe(frame, filename, network_schema=preprocessor.schema)
        issues = quality['issues']
        n = len(frame)
        rejected = np.zeros(n, dtype=bool)
        review = np.zeros(n, dtype=bool)
        page_end = min(n, offset + limit)
        page_findings = {i: [] for i in range(offset, page_end)}
        page_totals = {i: 0 for i in page_findings}
        page_categories = {i: set() for i in page_findings}
        page_reasons = {i: [] for i in page_findings}
        page_handled = {i: [] for i in page_findings}
        page_budget = MAX_PAGE_FINDINGS
        unlinked = 0
        for issue in issues:
            positions = issue.get('row_indices', issue.get('evidence', {}).get('row_indices', []))
            if not positions and issue.get('count', 0):
                unlinked += 1
            positions = np.asarray(positions, dtype=np.int64)
            if positions.size and ((positions < 0).any() or (positions >= n).any()):
                raise PredictionError('row_mapping_error', 'Quality findings contain incompatible source-row positions.', 500)
            column = issue.get('column')
            related = set(issue.get('columns', [])) | set((issue.get('relationship') or {}).get('conflicting_columns', []))
            relevant = column in required or bool(related.intersection(required))
            critical = relevant and issue['check'].startswith('network_invalid_')
            affects_review = (relevant and issue['category'] in {ERROR, QUALITY} and issue['check'] != 'duplicate') or (issue['check'] == 'duplicate' and self.duplicate_review)
            if critical:
                rejected[positions] = True
            elif affects_review:
                review[positions] = True
            for position in positions[(positions >= offset) & (positions < page_end)]:
                position = int(position)
                page_totals[position] += 1
                page_categories[position].add(issue['category'])
                if page_budget and len(page_findings[position]) < MAX_FINDINGS_PER_RECORD:
                    page_findings[position].append(compact_finding(issue))
                    page_budget -= 1
                if critical or affects_review:
                    reason = f"{issue['check'].replace('_', ' ')} in {column or ', '.join(sorted(related)) or 'duplicate record'}"
                    if critical:
                        page_reasons[position].insert(0, reason)
                    elif len(page_reasons[position]) < 5:
                        page_reasons[position].append(reason)
        # Existing schema validity rejects impossible inputs. Also detect the
        # estimator representation boundary, without clipping or changing rules.
        unseen_counts = {name: 0 for name in metadata['features']['categorical_features']}
        missing_counts = {name: 0 for name in required}
        numeric = set(metadata['features']['numeric_features'])
        normal = malicious = 0
        prediction_by_reliability = {'High': {'normal_count': 0, 'malicious_count': 0}, 'Review': {'normal_count': 0, 'malicious_count': 0}}
        probability_sum = 0.0
        record_predictions = {}
        for batch_start in range(0, n, self.predictor.batch_size):
            stop = min(n, batch_start + self.predictor.batch_size)
            batch = frame.iloc[batch_start:stop]
            normalized, _ = preprocess_network(batch.loc[:, required], preprocessor.schema, preprocessor.normalization_policy)
            for name in required:
                missing = missing_mask(normalized[name]).to_numpy(dtype=bool)
                positions = np.flatnonzero(missing) + batch_start
                review[positions] = True
                missing_counts[name] += int(missing.sum())
                for position in positions[(positions >= offset) & (positions < page_end)]:
                    method = 'saved training median' if name in numeric else 'saved missing-category indicator'
                    page_handled[int(position)].append({'column': name, 'method': method})
                    if len(page_reasons[int(position)]) < 5:
                        page_reasons[int(position)].append(f'Missing {name} handled by {method}')
                if name in numeric:
                    values = pd.to_numeric(normalized[name].where(~missing), errors='coerce').to_numpy(dtype=np.float64, na_value=np.nan)
                    invalid = ~missing & (~np.isfinite(values) | (np.abs(values) > np.finfo(np.float32).max))
                else:
                    invalid = np.zeros(len(batch), dtype=bool)
                    categories = metadata['features']['learned_categories'][name]
                    unseen = ~missing & ~normalized[name].astype(str).isin(categories).to_numpy()
                    unseen_counts[name] += int(unseen.sum())
                    unseen_positions = np.flatnonzero(unseen) + batch_start
                    review[unseen_positions] = True
                    for position in unseen_positions[(unseen_positions >= offset) & (unseen_positions < page_end)]:
                        if len(page_reasons[int(position)]) < 5:
                            page_reasons[int(position)].append(f'Unseen {name} uses saved all-zero encoding; training category information is unavailable')
                    # The reserved indicator is not a valid source value.
                    invalid |= normalized[name].astype(str).eq(MISSING_CATEGORY).to_numpy()
                invalid_positions = np.flatnonzero(invalid) + batch_start
                rejected[invalid_positions] = True
                for position in invalid_positions[(invalid_positions >= offset) & (invalid_positions < page_end)]:
                    page_reasons[int(position)].insert(0, f'Invalid {name}: incompatible with saved preprocessing or finite model representation')
            valid_positions = np.flatnonzero(~rejected[batch_start:stop]) + batch_start
            if not valid_positions.size:
                continue
            # Predict each row once, grouped by already-established integrity.
            # This supplies exact full-file class/reliability cross-counts without
            # keeping all predictions or inferring recommendations from a page.
            for reliability, needs_review in [('High', False), ('Review', True)]:
                selected = valid_positions[review[valid_positions] == needs_review]
                if not selected.size:
                    continue
                local_offset = int(np.searchsorted(selected, offset))
                local_limit = int(np.searchsorted(selected, page_end)) - local_offset
                result = self.predictor.predict(frame.iloc[selected], offset=local_offset, limit=max(local_limit, 0))
                normal += result['summary']['normal_count']
                malicious += result['summary']['malicious_count']
                for field in ['normal_count', 'malicious_count']:
                    prediction_by_reliability[reliability][field] += result['summary'][field]
                probability_sum += result['summary']['average_predicted_class_probability'] * len(selected)
                for record in result['records']:
                    source_position = int(selected[record['record_index']])
                    record_predictions[source_position] = {**record, 'record_index': source_position}
        records = []
        for position in range(offset, page_end):
            if rejected[position]:
                record = {'record_index': position, 'prediction': None, 'label': None,
                    'probability_normal': None, 'probability_malicious': None, 'predicted_class_probability': None}
                reliability = 'Low'
                reason = 'Prediction rejected: ' + '; '.join(page_reasons[position][:5])
                status = 'Rejected'
            else:
                record = record_predictions[position]
                reliability = 'Review' if review[position] else 'High'
                reason = ('Prediction produced; review input integrity: ' + '; '.join(page_reasons[position][:5])) if review[position] else 'Prediction produced with no unresolved predictive-field integrity issue. Analytical anomalies and preserved duplicates do not invalidate the input.'
                status = 'Predicted'
            records.append({**record, 'prediction_status': status,
                'quality_status': 'Issue detected' if page_totals[position] or review[position] or rejected[position] else 'No issue detected',
                'quality_findings': page_findings[position], 'quality_finding_count': page_totals[position],
                'quality_finding_categories': sorted(page_categories[position]),
                'quality_findings_truncated': page_totals[position] > len(page_findings[position]),
                'missing_predictive_fields': [item['column'] for item in page_handled[position]],
                'preprocessing_handled_missing': [] if rejected[position] else page_handled[position],
                'reliability': reliability, 'reliability_reason': reason})
        predicted = normal + malicious
        warnings = []
        if any(unseen_counts.values()):
            warnings.append('Unseen categories use saved encoding and require Review; no categories were learned.')
        if rejected.any():
            warnings.append('Invalid required values were rejected individually; rejected rows have no prediction or probability.')
        if unlinked:
            warnings.append('Some dataset findings have no row evidence and were not assigned to arbitrary records.')
        return {'filename': filename,
            'summary': {'records_analysed': n, 'records_predicted': predicted, 'normal_count': normal, 'malicious_count': malicious,
                'average_predicted_class_probability': probability_sum / predicted if predicted else None,
                'data_quality_score': quality['score'], 'grade': quality['grade'],
                'high_count': int((~review & ~rejected).sum()), 'review_count': int((review & ~rejected).sum()),
                'low_count': int(rejected.sum()), 'rejected_count': int(rejected.sum()),
                'processing_seconds': perf_counter() - start},
            'records': records,
            'pagination': {'offset': offset, 'limit': limit, 'returned_records': len(records), 'total_records': n,
                'next_offset': page_end if limit and page_end < n else None},
            'quality_summary': {'finding_summary': quality['finding_summary'], 'issue_summary': quality['issue_summary'],
                'score_policy': quality['score_policy'], 'unlinked_findings': unlinked},
            'quality_overview': quality_overview(quality, n),
            'prediction_by_reliability': prediction_by_reliability,
            'saved_evaluation': deepcopy(metadata.get('phase5_evaluation')),
            'schema_audit': {'unseen_categories': unseen_counts, 'missing_values': missing_counts, 'warnings': warnings},
            'model': {'selected_model': metadata['selected_model'], 'artifact_version': metadata['artifact_version'],
                'dataset_schema': preprocessor.schema.name,
                'encoded_feature_count': metadata['encoded_feature_count']},
            'reliability_policy': {'version': POLICY_VERSION, 'duplicate_review': self.duplicate_review,
                'probability_thresholds_used': False, 'low_means': 'Rejected due to invalid required input; no prediction was fabricated'},
            'probability_description': 'Model probability estimate, not calibrated certainty or input-data reliability.',
            'record_index_description': 'Zero-based position in original CSV data rows/DataFrame, excluding header.'}


combined_service = CombinedAnalysisService()


def analyze_network(dataframe, filename='uploaded.csv', *, offset=0, limit=100):
    return combined_service.analyze(dataframe, filename, offset=offset, limit=limit)
