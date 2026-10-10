"""Development evidence capture; run before applying Phase 2 engine changes."""
import json
from pathlib import Path
from pipeline import run_full_pipeline, run_pipeline_from_dataframe
import pandas as pd


def network_fixture():
    return pd.DataFrame({
        'id': [str(i) for i in range(40)],
        'dur': ['0.1'] * 38 + ['999999', '-1'],
        'proto': ['tcp'] * 35 + [' TCP ', 'udp', 'udp', 'icmp', 'icmp'],
        'service': ['-'] * 40, 'state': ['FIN'] * 40,
        'spkts': ['2'] * 38 + ['1000000', 'bad'],
        'dpkts': ['1'] * 40, 'sbytes': ['100'] * 40, 'dbytes': ['50'] * 40,
        'label': ['0'] * 20 + ['1'] * 20,
        'attack_cat': ['Normal'] * 20 + ['Exploits'] * 20,
    })


def compact(result):
    return {key: result[key] for key in ['filename', 'total_rows', 'total_columns',
        'score', 'grade', 'column_types', 'issues', 'score_policy', 'column_profiles']}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    output = root / 'docs/phase2'
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'baseline.json').exists():
        raise FileExistsError('Historical baseline already captured; use phase2_validate.py for repeatable comparisons.')
    fixture = output / 'fixtures/unsw_like_synthetic.csv'
    fixture.parent.mkdir(exist_ok=True)
    network_fixture().to_csv(fixture, index=False)
    files = sorted((root / 'backend/sample_data').rglob('*.csv'))
    reports = {str(path.relative_to(root)): compact(run_full_pipeline(path)) for path in files}
    reports['synthetic_network_not_UNSW_NB15'] = compact(run_pipeline_from_dataframe(network_fixture(), fixture.name))
    (output / 'baseline.json').write_text(json.dumps(reports, indent=2, allow_nan=False), encoding='utf-8')
    print('Baseline captured:', len(reports), 'datasets; actual UNSW-NB15 unavailable locally.')
