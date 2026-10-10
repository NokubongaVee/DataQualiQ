"""Validate and merge independently executed degradation groups."""
import csv
import json
from pathlib import Path
from experiments.data_quality_experiment import GROUPS, LEVELS, digest


def merge(output):
    numeric_path = output / 'experiment_results.json'
    reports = [json.loads(numeric_path.read_text())] + [
        json.loads((output / 'workers' / name / 'experiment_results.json').read_text())
        for name in ('categorical', 'representation')]
    configuration = reports[0]['configuration']
    baseline = reports[0]['conditions'][0]
    for report in reports:
        if report['configuration'] != configuration or report['conditions'][0] != baseline:
            raise ValueError('Configuration or measured baseline differs')
    for report in reports[1:]:
        if not report['complete'] or report['file_checksums_before'] != report['file_checksums_after']:
            raise ValueError('Worker incomplete or source files changed')
    hashes = reports[1]['file_checksums_after']
    if reports[2]['file_checksums_after'] != hashes:
        raise ValueError('Worker integrity checks differ')
    if any(digest(Path(path)) != expected for path, expected in hashes.items()):
        raise ValueError('Current source files differ from checked worker inputs')
    conditions = [baseline]
    for kind in GROUPS:
        for level in LEVELS:
            matches = [item for report in reports for item in report['conditions']
                       if item['condition'] == kind and item['degradation_percent'] == level * 100]
            if len(matches) != 1:
                raise ValueError('Missing or duplicated measured condition')
            conditions.extend(matches)
    checkpoint = output / 'workers' / 'numeric'
    checkpoint.mkdir(parents=True, exist_ok=True)
    (checkpoint / 'experiment_results.json').write_text(json.dumps(reports[0], indent=2))
    result = dict(reports[0], conditions=conditions, complete=True, files_unchanged=True,
                  file_checksums_before=hashes, file_checksums_after=hashes,
                  execution='Baseline and numeric group serial; categorical and representation groups in isolated concurrent processes sharing the measured baseline',
                  summed_condition_seconds=sum(item['seconds'] for item in conditions))
    (output / 'experiment_results.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    fields = ['condition', 'degradation_percent', 'quality_score', 'grade', 'accuracy', 'precision', 'recall', 'f1', 'false_positives', 'false_negatives', 'high_count', 'review_count', 'low_count', 'rejected_count', 'recall_change_pp', 'false_negative_change', 'affected_values', 'affected_rows', 'seconds']
    with (output / 'experiment_results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in conditions:
            row = {name: item[name] for name in fields if name in item}
            row.update(recall_change_pp=100 * item['changes_from_baseline']['recall'],
                       false_negative_change=item['changes_from_baseline']['false_negatives'],
                       affected_values=item['degradation']['affected_values'], affected_rows=item['degradation']['affected_rows'])
            writer.writerow(row)
    print('Validated all ten full-data conditions and unchanged source/artifact hashes.')
    return result


if __name__ == '__main__':
    merge(Path(__file__).resolve().parents[2] / 'docs/phase16')
