"""Repeatable development validation. Does not write source CSVs or train models.

Reports all triggered rules, check coverage and conservative preprocessing audits.
An optional --unsw path is explicitly schema-configured, never filename-inferred.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from types import FunctionType
import pandas as pd
from csv_loading import load_csv
from pipeline import run_pipeline_from_dataframe
from domains.network.configs import unsw_nb15_schema
from domains.network import NetworkSchema, FieldRule
from preprocessing import FieldPolicy, PreprocessingPolicy, preprocess_network

ROOT = Path(__file__).resolve().parents[1]


def legacy_engine():
    # pipeline/scoring were unchanged in the user's pre-Phase-2 worktree.
    # Capture their original orchestration and score for a like-for-like audit.
    sources = {name: subprocess.check_output(['git','show',f'HEAD:backend/{name}.py'],cwd=ROOT).decode('utf-8')
               for name in ('pipeline','scoring','validity_checks','type_inference')}
    score_namespace, pipeline_namespace = {}, {'__name__':'phase2_legacy_pipeline'}
    exec(compile(sources['scoring'],'legacy_scoring.py','exec'),score_namespace)
    exec(compile(sources['pipeline'],'legacy_pipeline.py','exec'),pipeline_namespace)
    pipeline_namespace['calculate_quality_score'] = score_namespace['calculate_quality_score']
    original_types = {}
    exec(compile(sources['type_inference'],'legacy_type_inference.py','exec'),original_types)
    pipeline_namespace['infer_all_column_profiles'] = original_types['infer_all_column_profiles']
    original_validity = {}
    exec(compile(sources['validity_checks'],'legacy_validity.py','exec'),original_validity)
    current = pipeline_namespace['run_selected_checks']
    checks = {**current.__globals__['VALIDITY_CHECKS'], 'numeric': original_validity['check_numeric_bounds']}
    pipeline_namespace['run_selected_checks'] = FunctionType(current.__code__,
        {**current.__globals__, 'VALIDITY_CHECKS': checks}, current.__name__, current.__defaults__)
    return pipeline_namespace['run_pipeline_from_dataframe']


def rule_decision(issue):
    check=issue['check']
    if check.startswith('network_'):
        return 'DOMAIN-SPECIFIC', 'Independent explicit schema constraint; no target- or frequency-derived validity.'
    if check=='outlier':
        return 'MODIFY', 'Keep IQR observations and source values; remove their quality-error penalty.'
    if check=='invalid_categorical':
        return 'MODIFY', 'Edit-distance rarity suggests review only; no invalidity or automatic correction. Schema vocabulary overrides this detector.'
    if check=='invalid_phone':
        return 'MODIFY', 'Keep actual contact syntax checks; numeric-dominant unnamed decimal measurements must not be routed as phone numbers.'
    if check=='invalid_numeric':
        return 'MODIFY', 'Validate finite decimal syntax separately from floating-point representation limits.'
    if check in {'header_conflict','repeated_identifier','relationship_deviation','pattern_deviation','ambiguous_date'}:
        return 'KEEP', 'Evidence-backed review candidate; not an established business constraint.'
    return 'KEEP', 'Generic observable missingness, duplication, representation or parse failure; no network-specific assumptions.'


def compact(result):
    by_check=Counter()
    for finding in result['issues']:
        by_check[finding['check']]+=finding['count']
    return {'rows':result['total_rows'],'columns':result['total_columns'],
        'score':result['score'],'grade':result['grade'],'score_policy':result['score_policy'],
        'occurrences_by_check':dict(by_check),'inferred_or_configured_types':result['column_types'],
        'types_before_schema':{name:profile.get('inferred_type',profile['type']) for name,profile in result['column_profiles'].items()},
        'check_coverage':{name:profile['checks'] for name,profile in result['column_profiles'].items()},
        'warnings':result.get('domain_validation',{}).get('warnings',[]),
        'finding_summary':result.get('finding_summary',{}),
        'findings':[{'check':i['check'],'column':i.get('column'),'count':i['count'],
            'pct':i['pct'],'denominator':i.get('denominator'),'category':i.get('category','legacy_unclassified'),
            'sample_source_rows':i['row_indices'][:10], 'decision':rule_decision(i)[0],
            'rationale':rule_decision(i)[1]} for i in result['issues']]}


def compact_audit(audit):
    def summary(item):
        keys = ('unchanged_rows','changed_rows','excluded_rows','numerically_preserved_rows')
        return {**{k:v for k,v in item.items() if k not in keys},
                **{k+'_count':len(item.get(k,[])) for k in keys}}
    return {**{k:v for k,v in audit.items() if k not in {'detected_findings','finding_statuses','unchanged_findings','preserved_anomalies','output_source_row_positions'}},
            'finding_statuses':[summary(item) for item in audit['finding_statuses']],
            'unchanged_findings':[summary(item) for item in audit['unchanged_findings']],
            'preserved_anomalies':[summary(item) for item in audit['preserved_anomalies']]}


def validate_file(path, schema, before_engine):
    raw=path.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    frame=load_csv(raw)
    print(f'Assessing baseline: {path.name} ({len(frame):,} rows)',flush=True)
    baseline=compact(before_engine(frame,path.name))
    print(f'Assessing configured pipeline: {path.name}',flush=True)
    assessed=run_pipeline_from_dataframe(frame,path.name,network_schema=schema)
    after=compact(assessed)
    # Only protocol case/outer whitespace is demonstrably representation-only
    # under this explicitly case-insensitive schema. Never fit an imputer here.
    protocol=next((name for name,rule in schema.fields.items() if rule.kind=='protocol' and not rule.case_sensitive),None) if schema else None
    policy=PreprocessingPolicy(fields={protocol:FieldPolicy(trim=True,case='lower',
        reason='Explicit schema declares protocol representation case-insensitive.')} if protocol and protocol in frame else {})
    print(f'Checking conservative preprocessing: {path.name}',flush=True)
    if schema:
        processed,audit=preprocess_network(frame,schema,policy,assessed['issues'])
    else:
        from preprocessing import preprocess_dataframe
        processed,audit=preprocess_dataframe(frame,policy,assessed['issues'])
    for protected in (schema.protected_fields if schema else frozenset()) & set(frame.columns):
        pd.testing.assert_series_equal(frame[protected],processed[protected])
    assert len(processed)==len(frame)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    return {'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        'sha256':digest,'baseline':baseline,'phase2':after,'preprocessing':compact_audit(audit),
        'source_unchanged':True, 'target_fields_unchanged':True,
        'all_rows_preserved':True,'model_training_performed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unsw',action='append',type=Path,default=[])
    args=parser.parse_args()
    before=legacy_engine()
    files=[(path,None) for path in sorted((ROOT/'backend/sample_data').rglob('*.csv'))]
    files.append((ROOT/'docs/phase2/fixtures/unsw_like_synthetic.csv',unsw_nb15_schema()))
    files.append((ROOT/'docs/phase2/fixtures/alternate_network.csv',NetworkSchema(name='alternate_flow_export',fields={
        'protocol':FieldRule('protocol',case_sensitive=False),'duration_seconds':FieldRule('nonnegative'),
        'packets_sent':FieldRule('count'),'packets_received':FieldRule('count'),
        'bytes_sent':FieldRule('count'),'bytes_received':FieldRule('count')})))
    files.extend((path.resolve(),unsw_nb15_schema()) for path in args.unsw)
    reports=[]
    for path,schema in files:
        reports.append(validate_file(path,schema,before))
    report={'scope':'Phase 2 only; no model fitting or predictions',
            'baseline_method':'Original HEAD pipeline/scoring/type inference/numeric detector with preserved existing other generic detectors; no network schema. Added uncertain-category review metadata does not change detection counts.',
            'datasets':reports}
    output=ROOT/'docs/phase2/validation.json'
    output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print('Saved',output,flush=True)


if __name__=='__main__': main()
