"""Phase 9 wire contract and evidence-based human decision support."""
from copy import deepcopy
import math
from .prediction import PredictionError


def model_performance(result):
    evaluation = result.get('saved_evaluation')
    try:
        metrics = evaluation['metrics']
        required = {name: float(metrics[name]) for name in ['accuracy', 'precision', 'recall', 'f1']}
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in required.values()):
            raise ValueError('Invalid saved metrics')
        matrix = evaluation['confusion_matrix']
        if (len(matrix) != 2 or any(len(row) != 2 for row in matrix) or
                any(type(value) is not int or value < 0 for row in matrix for value in row) or
                sum(sum(row) for row in matrix) != evaluation['records'] or
                evaluation['positive_class'] != 1 or evaluation['confusion_matrix_labels'] != [0, 1]):
            raise ValueError('Invalid saved confusion matrix')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PredictionError('evaluation_unavailable', 'Saved official model evaluation is missing or invalid. Restore compatible model metadata.', 503) from exc
    return {'source': 'official_test_evaluation',
        'dataset': result['model']['dataset_schema'] + ' reserved official testing split',
        'is_current_upload_metric': False, 'evaluation_phase': 5,
        'model': result['model']['selected_model'], 'artifact_version': result['model']['artifact_version'],
        'records_evaluated': evaluation['records'], 'positive_class': 1, 'positive_class_label': 'Malicious',
        **required, 'confusion_matrix': deepcopy(matrix), 'confusion_matrix_labels': [0, 1],
        'confusion_matrix_orientation': 'Rows actual, columns predicted; labels 0=Normal, 1=Malicious.',
        'interpretation': 'Saved Phase 5 results; not calculated from this upload. Model selection used this test split, so these are not a fresh independent estimate of the selected winner.'}


def recommendations(result):
    summary = result['summary']
    quality = result['quality_overview']
    output = []
    def add(priority, message, reason, count):
        if count:
            output.append({'priority': priority, 'message': message, 'reason': reason, 'affected_records': int(count)})
    review_malicious = result['prediction_by_reliability']['Review']['malicious_count']
    add('high', 'Prioritise human review of malicious predictions with input-integrity issues.',
        f'Malicious predictions requiring Review: {review_malicious}. Input issues may affect interpretation.', review_malicious)
    add('high', 'Investigate model-predicted malicious records using independent security evidence.',
        f"{summary['malicious_count']} records were predicted Malicious. A probability estimate does not establish a confirmed attack.", summary['malicious_count'])
    add('high', 'Inspect rejected records and correct their predictive inputs before reanalysis.',
        f"{summary['rejected_count']} records could not be safely predicted; their classes and probabilities are unavailable.", summary['rejected_count'])
    missing = quality['missing_values']['affected_records']
    add('medium', 'Review missing source values before relying on affected records.',
        f'{missing} records have missing-value findings. Saved preprocessing handles compatible missing predictive cells; it does not prove source completeness.', missing)
    invalid = quality['invalid_values']['affected_records']
    add('high', 'Verify structurally invalid fields against the original source.',
        f'{invalid} records have data-error findings. Invalid required predictors are rejected; ancillary-field errors may not affect prediction.', invalid)
    anomalies = quality['analytical_anomalies']['affected_records']
    add('medium', 'Preserve analytical anomalies for contextual security investigation.',
        f'{anomalies} distinct records have analytical findings; these are not automatically bad input or confirmed attacks.', anomalies)
    duplicates = quality['duplicates']['affected_records']
    add('medium', 'Check duplicate event provenance before changing record counts.',
        f'{duplicates} excess duplicate records were preserved. Repeated observations may be legitimate events.', duplicates)
    return output


def format_combined_api_response(result):
    summary = result['summary']
    quality = deepcopy(result['quality_overview'])
    quality['warnings'] = list(result['schema_audit']['warnings'])
    quality['schema_audit'] = deepcopy(result['schema_audit'])
    quality['unlinked_findings'] = result['quality_summary']['unlinked_findings']
    pagination = dict(result['pagination'])
    pagination['has_more'] = pagination['offset'] + pagination['returned_records'] < pagination['total_records']
    records = [{**record, 'rejection_reason': record['reliability_reason'] if record['prediction_status'] == 'Rejected' else None}
               for record in result['records']]
    return {'filename': result['filename'], 'data_quality': quality,
        'intrusion_summary': {**{key: summary[key] for key in ['records_analysed', 'records_predicted', 'rejected_count', 'normal_count', 'malicious_count', 'average_predicted_class_probability', 'processing_seconds']},
            'probability_description': result['probability_description']},
        'model_performance': model_performance(result),
        'reliability_summary': {**{key: summary[key] for key in ['high_count', 'review_count', 'low_count', 'rejected_count']},
            'prediction_by_reliability': deepcopy(result['prediction_by_reliability']),
            'policy': deepcopy(result['reliability_policy']),
            'interpretation': 'Input integrity, separate from model probability and dataset quality score; Low rows were rejected.'},
        'records': records, 'pagination': pagination, 'recommendations': recommendations(result)}
