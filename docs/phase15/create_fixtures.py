"""Generate temporary upload fixtures without changing original data or targets."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from csv_loading import load_csv
root = Path(__file__).resolve().parents[2]
base = load_csv((root / 'data/UNSW_NB15_testing-set.csv').read_bytes()).iloc[:20].drop(columns=['label', 'attack_cat'], errors='ignore').copy()
output = Path(sys.argv[1])
cases = []
def save(name, frame, description, expected, error=False):
    path = output / (name + '.csv')
    path.write_text(frame if isinstance(frame, str) else frame.to_csv(index=False), encoding='utf-8')
    cases.append({'name': name, 'path': str(path), 'description': description, 'expected': expected, 'rows': 0 if isinstance(frame, str) else len(frame), 'error': error})
save('good_csv', base, '20 official testing rows without target labels', '20 predictions; real quality, probability and reliability')
save('malformed_csv', 'a,b\n"unterminated,2\n', 'Unclosed quoted CSV field', 'Clear malformed CSV error', True)
save('missing_features', base.drop(columns=['dur', 'proto', 'spkts']), 'Required dur, proto, spkts removed', 'Missing fields listed safely', True)
missing = base.copy(); missing.loc[0, 'dur'] = ''; missing.loc[1, 'service'] = ''
save('missing_values', missing, 'Missing dur numeric and service categorical cells', 'Missing findings, saved handling and Review; predictions retained')
invalid = base.copy(); invalid.loc[0, 'dur'] = '-1'
save('invalid_numeric', invalid, 'Negative duration violates structural nonnegative rule', 'Invalid finding, rejected row with null class/probability')
unseen = base.copy(); unseen.loc[0, 'proto'] = 'phase15-unseen-proto'
save('unseen_category', unseen, 'Structurally valid unseen protocol token', 'Unseen audit, saved encoding, Review without retraining')
extreme = base.copy(); extreme.loc[len(extreme)-1, 'dur'] = '100000000'
save('analytical_outlier', extreme, 'Valid extreme duration in last row', 'Analytical finding; no rejection or reliability downgrade solely for outlier')
import pandas as pd
duplicates = pd.concat([base, base.iloc[[0]]], ignore_index=True)
save('duplicates', duplicates, 'One exact repeated row including same identifier', 'Duplicate detected, records preserved, no automatic Low')
print(json.dumps(cases))
