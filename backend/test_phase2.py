"""Phase 2 behavioural invariants, using generic and alternate network schemas."""
import asyncio
import io
import json
import unittest
import pandas as pd
from starlette.datastructures import UploadFile
from fastapi import HTTPException
from csv_loading import load_csv
from pipeline import run_pipeline_from_dataframe
from generic_checks import check_missing, check_duplicate_rows, check_categorical_format
from domains.network import NetworkSchema, FieldRule, validate_network
from domains.network.configs import unsw_nb15_schema
from preprocessing import FieldPolicy, PreprocessingPolicy, preprocess_dataframe, preprocess_network
from main import assess_csv


def alternate_schema():
    return NetworkSchema(name='alternate_flows', fields={
        'protocol': FieldRule('protocol', case_sensitive=False),
        'duration_seconds': FieldRule('nonnegative'), 'packets_sent': FieldRule('count'),
        'packets_received': FieldRule('count'), 'bytes_sent': FieldRule('count'),
        'bytes_received': FieldRule('count'), 'destination_port': FieldRule('port'),
        'flag': FieldRule('binary'), 'source_ip': FieldRule('ip')},
        target_fields=('truth',), leakage_fields=('attack_kind',), identifier_fields=('flow_id',))


def network_frame():
    return pd.DataFrame({'protocol': ['tcp'] * 8 + [' TCP ', 'newproto'],
        'duration_seconds': ['0.1'] * 8 + ['999999', '-1'],
        'packets_sent': ['2'] * 8 + ['1000000', 'bad'], 'packets_received': ['1'] * 10,
        'bytes_sent': ['20'] * 10, 'bytes_received': ['10'] * 10,
        'destination_port': ['443'] * 8 + ['65535', '65536'], 'flag': ['0'] * 9 + ['2'],
        'source_ip': ['192.0.2.1'] * 9 + ['broken'], 'flow_id': [str(i) for i in range(10)],
        'truth': ['0'] * 5 + ['1'] * 4 + [''], 'attack_kind': ['Normal'] * 5 + ['Other'] * 5})


class Phase2Tests(unittest.TestCase):
    def test_generic_missing_duplicates_and_representation(self):
        frame = pd.DataFrame({'customer': ['A', 'A', 'B'], 'category': [' Gold ', 'gold', ''], 'amount': ['1', '1', 'NA']})
        self.assertEqual(check_missing(frame, 'amount')['row_indices'], [2])
        self.assertEqual(check_categorical_format(frame, 'category')['count'], 1)
        self.assertEqual(check_duplicate_rows(pd.concat([frame, frame.iloc[[0]]], ignore_index=True))['count'], 1)

    def test_generic_compatibility_and_opt_in_domain(self):
        for frame in [pd.DataFrame({'customer_id': ['C1','C2','C3'], 'email':['a@example.org','b@example.org','']}),
                      pd.DataFrame({'x':list(range(20)) + [999999]}),
                      pd.DataFrame({'group':['AAA'] * 20 + ['aaa','Other']}), network_frame()]:
            result = run_pipeline_from_dataframe(frame)
            self.assertFalse(result['domain_validation']['enabled'])
            self.assertFalse(any(i['check'].startswith('network_') for i in result['issues']))
            json.dumps(result, allow_nan=False)

    def test_malformed_csv_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Malformed CSV'):
            load_csv(b'a,b\n1,2,3\n')

    def test_domain_rules_and_no_vocabulary_learning(self):
        result = run_pipeline_from_dataframe(network_frame(), network_schema=alternate_schema())
        checks = {i['check'] for i in result['issues']}
        self.assertTrue({'network_invalid_nonnegative','network_invalid_count','network_invalid_port',
                         'network_invalid_binary','network_invalid_ip'} <= checks)
        self.assertNotIn('network_invalid_protocol', checks)
        self.assertNotIn('invalid_categorical', checks)
        self.assertEqual(result['column_types']['packets_sent'], 'numeric')

    def test_mapping_is_independent_of_dataset_names(self):
        frame = network_frame()
        mapping = {'protocol':'wire_kind', 'duration_seconds':'elapsed', 'packets_sent':'outbound',
                   'packets_received':'inbound', 'bytes_sent':'octets_out', 'bytes_received':'octets_in',
                   'destination_port':'endpoint', 'flag':'indicator', 'source_ip':'address'}
        schema = alternate_schema()
        renamed = NetworkSchema(fields={mapping.get(k,k):v for k,v in schema.fields.items()})
        before, _ = validate_network(frame, schema)
        after, _ = validate_network(frame.rename(columns=mapping), renamed)
        self.assertEqual([(i['check'],mapping.get(i['column'],i['column']),i['row_indices']) for i in before],
                         [(i['check'],i['column'],i['row_indices']) for i in after])

    def test_domain_boundary_values(self):
        frame = pd.DataFrame({'p':['0','65535','65536','-1','1.5','bad',''],
                              'n':['0','1','1.5','-1','Infinity','1e3',''],
                              'proto':['tcp','udp','icmp','255','256','x y','']})
        findings, _ = validate_network(frame, NetworkSchema(fields={'p':FieldRule('port'),'n':FieldRule('count'),'proto':FieldRule('protocol')}))
        rows = {i['column']: i['row_indices'] for i in findings}
        self.assertEqual(rows['p'],[2,3,4,5]); self.assertEqual(rows['n'],[2,3,4]); self.assertEqual(rows['proto'],[4,5])

    def test_protocol_names_with_registered_punctuation_are_preserved(self):
        frame=pd.DataFrame({'wire':['3pc','ax.25','tp++','a/n','new-proto','6','255','tcp?','x y']})
        findings,_=validate_network(frame,NetworkSchema(fields={'wire':FieldRule('protocol')}))
        self.assertEqual(findings[0]['row_indices'],[7,8])
        output,_=preprocess_network(frame,NetworkSchema(fields={'wire':FieldRule('protocol')}))
        pd.testing.assert_frame_equal(output,frame)

    def test_long_decimals_remain_generic_numeric_measurements(self):
        from type_inference import infer_column_profile
        durations=pd.Series(['0.121478','0.649902','1.623129','1.681642','0.449454'] * 5)
        self.assertEqual(infer_column_profile(durations,'arbitrary_measurement')['type'],'numeric')
        result=run_pipeline_from_dataframe(pd.DataFrame({'elapsed':durations}))
        self.assertFalse(any(i['check']=='invalid_phone' for i in result['issues']))
        phones=pd.Series(['+27 82 123 4567','+27 83 123 4567'] * 5)
        self.assertEqual(infer_column_profile(phones,'anonymous')['type'],'phone')

    def test_required_and_optional_schema_fields(self):
        frame = pd.DataFrame({'a':['1','2']})
        findings, warnings = validate_network(frame, NetworkSchema(fields={'required':FieldRule('port',required=True),'optional':FieldRule('count')}))
        self.assertEqual(len(warnings),2); self.assertEqual(findings[0]['category'],'data_error')
        result = run_pipeline_from_dataframe(frame, network_schema=NetworkSchema(fields={'absent':FieldRule('port',required=True)}))
        self.assertEqual(result['issues'][-1]['check'],'network_missing_field')

    def test_outliers_preserved_without_quality_penalty(self):
        frame = pd.DataFrame({'record_id':list(range(20)), 'reading':['1'] * 19 + ['1000000000']})
        assessment = run_pipeline_from_dataframe(frame)
        self.assertEqual(assessment['score'],100)
        outlier = next(i for i in assessment['issues'] if i['check']=='outlier')
        self.assertEqual(outlier['category'],'analytical_security_anomaly')
        output, audit = preprocess_dataframe(frame, findings=assessment['issues'])
        pd.testing.assert_frame_equal(output,frame)
        self.assertEqual(audit['preserved_anomalies'][0]['unchanged_rows'],[19])

    def test_default_preprocessor_is_identity(self):
        frame = network_frame(); assessment = run_pipeline_from_dataframe(frame, network_schema=alternate_schema())
        output, audit = preprocess_network(frame, alternate_schema(), findings=assessment['issues'])
        pd.testing.assert_frame_equal(output,frame)
        self.assertEqual(audit['automatic_corrections'],[]); self.assertEqual(audit['rows_affected'],0)

    def test_normalization_numeric_and_invalid_audit(self):
        frame = network_frame(); source = frame.copy(deep=True)
        plan = PreprocessingPolicy(fields={
            'protocol':FieldPolicy(trim=True,case='lower',reason='Protocol spelling is case-insensitive under this schema.'),
            'packets_sent':FieldPolicy(numeric=True,invalid='mark_missing',reason='Verified packet counts; malformed values remain unknown.'),
            'duration_seconds':FieldPolicy(numeric=True,invalid='mark_missing',reason='Duration cannot be negative.')}, include_examples=True)
        result = run_pipeline_from_dataframe(frame, network_schema=alternate_schema())
        output,audit = preprocess_network(frame,alternate_schema(),plan,result['issues'])
        pd.testing.assert_frame_equal(frame,source)
        self.assertEqual(output.loc[8,'protocol'],'tcp'); self.assertEqual(output.loc[8,'duration_seconds'],999999)
        self.assertTrue(pd.isna(output.loc[9,'packets_sent'])); self.assertTrue(pd.isna(output.loc[9,'duration_seconds']))
        self.assertTrue(audit['automatic_corrections'])
        for item in audit['automatic_corrections']:
            self.assertTrue({'column','operation','rows_affected','source_row_positions','reason','category','rule','safe'} <= set(item))
        self.assertTrue(any(item['changed_rows'] for item in audit['finding_statuses']))
        json.dumps(audit,allow_nan=False)

    def test_target_and_leakage_fields_protected(self):
        frame = network_frame(); schema = alternate_schema()
        for name in ('truth','attack_kind','flow_id'):
            with self.assertRaisesRegex(ValueError,'Protected field'):
                preprocess_network(frame,schema,PreprocessingPolicy(fields={name:FieldPolicy(trim=True,reason='test')}))
        output,_ = preprocess_network(frame,schema)
        self.assertEqual(output.loc[9,'truth'],'')

    def test_targets_do_not_decide_feature_validity(self):
        frame = network_frame(); schema=alternate_schema()
        a=run_pipeline_from_dataframe(frame,network_schema=schema)
        frame['truth']=['999'] * len(frame); frame['attack_kind']=['totally different'] * len(frame)
        b=run_pipeline_from_dataframe(frame,network_schema=schema)
        def signatures(result):
            return [(i['check'],i['column'],i['row_indices']) for i in result['issues'] if i['column'] not in schema.protected_fields and i['check']!='duplicate']
        self.assertEqual(signatures(a),signatures(b))
        self.assertFalse(any('truth' in str(i) or 'attack_kind' in str(i) for i in a['relationships']['observations']))

    def test_duplicates_detected_but_removal_requires_policy(self):
        frame = pd.DataFrame({'a':['1','1','2']})
        output,audit=preprocess_dataframe(frame)
        pd.testing.assert_frame_equal(output,frame); self.assertEqual(audit['duplicates']['detected_excess_rows'],1)
        with self.assertRaises(ValueError): PreprocessingPolicy(duplicate_policy='remove_exact')
        policy=PreprocessingPolicy(duplicate_policy='remove_exact',allow_duplicate_removal=True,duplicate_reason='Verified repeated import.')
        output,audit=preprocess_dataframe(frame,policy)
        self.assertEqual(len(output),2); self.assertEqual(audit['excluded_source_rows'],[1])

    def test_normalized_equivalent_rows_are_not_deleted_as_exact_duplicates(self):
        frame=pd.DataFrame({'a':[' TCP ','tcp']})
        policy=PreprocessingPolicy(fields={'a':FieldPolicy(trim=True,case='lower',reason='Case-insensitive protocol.')},
            duplicate_policy='remove_exact',allow_duplicate_removal=True,duplicate_reason='Verified exact duplicates only.')
        output,_=preprocess_dataframe(frame,policy)
        self.assertEqual(len(output),2)

    def test_missing_policies_preserve_constant_or_reject(self):
        frame=pd.DataFrame({'a':['','known','NA'], 'x':['1','2','3']})
        output,_=preprocess_dataframe(frame,PreprocessingPolicy(fields={'a':FieldPolicy(missing='constant',fill_value='unknown',reason='Explicit unknown category approved.')}))
        self.assertEqual(output['a'].tolist(),['unknown','known','unknown'])
        output,audit=preprocess_dataframe(frame,PreprocessingPolicy(fields={'a':FieldPolicy(missing='reject',reason='Critical required observation.')}))
        self.assertEqual(output.index.tolist(),[1]); self.assertEqual(audit['excluded_source_rows'],[0,2])
        with self.assertRaises(ValueError): FieldPolicy(missing='median',reason='Not fitted on training.')

    def test_lossy_numbers_remain_raw_and_valid_extremes_are_not_capped(self):
        frame=pd.DataFrame({'x':['9007199254740993','1e400','1','2','bad']})
        policy=PreprocessingPolicy(fields={'x':FieldPolicy(numeric=True,invalid='mark_missing',reason='Known numeric field.')})
        output,audit=preprocess_dataframe(frame,policy)
        self.assertEqual(output.loc[0,'x'],'9007199254740993'); self.assertEqual(output.loc[1,'x'],'1e400')
        self.assertTrue(pd.isna(output.loc[4,'x']))
        self.assertEqual(audit['skipped_operations'][0]['source_row_positions'],[0,1])

    def test_generic_numeric_validity_does_not_confuse_overflow_with_bad_data(self):
        from validity_checks import check_numeric_bounds
        frame=pd.DataFrame({'x':['1','2','1e400','9007199254740993','bad','inf']})
        finding=check_numeric_bounds(frame,'x')
        self.assertEqual(finding['row_indices'],[4,5])

    def test_lossless_numeric_cast_preserves_anomaly_magnitude(self):
        frame=pd.DataFrame({'reading':['1'] * 19 + ['1000000000']})
        findings=[{'check':'outlier','column':'reading','count':1,'row_indices':[19]}]
        policy=PreprocessingPolicy(fields={'reading':FieldPolicy(numeric=True,reason='Known numeric representation.')})
        output,audit=preprocess_dataframe(frame,policy,findings)
        self.assertEqual(output.loc[19,'reading'],1000000000)
        self.assertEqual(audit['preserved_anomalies'][0]['numerically_preserved_rows'],[19])

    def test_already_numeric_values_keep_dtype_without_silent_changes(self):
        frame=pd.DataFrame({'x':[1,2,3]})
        policy=PreprocessingPolicy(fields={'x':FieldPolicy(numeric=True,reason='Known numeric representation.')})
        output,audit=preprocess_dataframe(frame,policy)
        pd.testing.assert_frame_equal(output,frame)
        self.assertEqual(audit['automatic_corrections'],[])

    def test_duplicate_indexes_have_unambiguous_source_positions(self):
        frame=pd.DataFrame({'a':[' A ',' B ']},index=[10,10])
        output,audit=preprocess_dataframe(frame,PreprocessingPolicy(fields={'a':FieldPolicy(trim=True,reason='Outer spaces insignificant.')}))
        self.assertEqual(output.index.tolist(),[10,10]); self.assertEqual(audit['source_rows_affected'],[0,1])

    def test_schema_serialization_and_configuration_validation(self):
        schema=alternate_schema()
        self.assertEqual(NetworkSchema.from_dict(json.loads(json.dumps(schema.to_dict()))),schema)
        with self.assertRaises(ValueError): FieldRule('made_up')
        with self.assertRaises(ValueError): FieldRule('port',required='false')
        with self.assertRaises(ValueError): NetworkSchema(target_fields='label')
        with self.assertRaises(ValueError): FieldPolicy(trim=True)
        with self.assertRaises(ValueError): FieldPolicy(trim='false',reason='Invalid configuration.')
        with self.assertRaises(ValueError): PreprocessingPolicy(allow_duplicate_removal='false')
        with self.assertRaises(ValueError): preprocess_dataframe(pd.DataFrame({'a':['1']}),PreprocessingPolicy(fields={'nope':FieldPolicy()}))

    def test_exact_duplicate_removal_is_reported_separately_from_anomaly_preservation(self):
        frame=pd.DataFrame({'id':['1','2','2'], 'reading':['1','999999','999999']})
        findings=[{'check':'outlier','column':'reading','count':2,'row_indices':[1,2]}]
        policy=PreprocessingPolicy(duplicate_policy='remove_exact',allow_duplicate_removal=True,duplicate_reason='Verified duplicated export record.')
        output,audit=preprocess_dataframe(frame,policy,findings)
        self.assertEqual(output['reading'].tolist(),['1','999999'])
        self.assertEqual(audit['preserved_anomalies'][0]['unchanged_rows'],[1])
        self.assertEqual(audit['preserved_anomalies'][0]['excluded_rows'],[2])

    def test_spelling_candidates_are_quality_reviews_not_proven_errors(self):
        frame=pd.DataFrame({'record_id':list(range(100)), 'kind':['normaltype'] * 99 + ['normaltyp']})
        assessment=run_pipeline_from_dataframe(frame)
        finding=next(i for i in assessment['issues'] if i['check']=='invalid_categorical')
        self.assertEqual(finding['category'],'quality_issue'); self.assertTrue(finding['review_only'])
        self.assertEqual(assessment['score'],100)
        output,_=preprocess_dataframe(frame,findings=assessment['issues'])
        pd.testing.assert_frame_equal(output,frame)

    def test_schema_forbids_case_changes_when_meaningful_and_bad_fill(self):
        frame=pd.DataFrame({'state':['FIN'], 'packets':['']})
        schema=NetworkSchema(fields={'state':FieldRule('category',case_sensitive=True),'packets':FieldRule('count')})
        with self.assertRaises(ValueError): preprocess_network(frame,schema,PreprocessingPolicy(fields={'state':FieldPolicy(case='lower',reason='Not safe.')}))
        with self.assertRaises(ValueError): preprocess_network(frame,schema,PreprocessingPolicy(fields={'packets':FieldPolicy(missing='constant',fill_value=-1,reason='Not valid.')}))

    def test_unsw_specific_mapping_is_isolated_and_no_model_runs(self):
        schema=unsw_nb15_schema()
        self.assertEqual(schema.target_fields,('label',)); self.assertTrue({'id','attack_cat','label'} <= schema.protected_fields)
        self.assertEqual(schema.feature_columns(['id','dur','proto','attack_cat','label']),['dur','proto'])
        self.assertEqual(schema.fields['is_ftp_login'].kind,'nonnegative')
        frame=pd.DataFrame({'proto':['tcp','udp'], 'dur':['0','-1'], 'label':['0','2']})
        result=run_pipeline_from_dataframe(frame,network_schema=schema)
        self.assertNotIn('intrusion_detection',result)
        self.assertTrue(any(i['check']=='network_invalid_binary' and i['column']=='label' for i in result['issues']))

    def test_api_remains_read_only_and_supports_optional_schema(self):
        content=b'protocol,packets\ntcp,-1\nudp,2\n'
        schema=NetworkSchema(fields={'protocol':FieldRule('protocol'),'packets':FieldRule('count')})
        async def run(config):
            file=UploadFile(filename='flows.csv',file=io.BytesIO(content))
            return await assess_csv(file,config)
        generic=json.loads(asyncio.run(run(None)).body)
        network=json.loads(asyncio.run(run(json.dumps(schema.to_dict()))).body)
        self.assertFalse(generic['domain_validation']['enabled'])
        self.assertTrue(network['domain_validation']['enabled'])
        self.assertTrue(any(i['check']=='network_invalid_count' for i in network['issues']))
        with self.assertRaises(HTTPException) as caught: asyncio.run(run('{bad'))
        self.assertEqual(caught.exception.status_code,400)


if __name__=='__main__': unittest.main()
