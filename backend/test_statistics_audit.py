"""Independent CSV arithmetic audit; no detection/scoring policy changes."""
import csv
import json
import math
import statistics
import unittest
from collections import Counter
from pathlib import Path
import pandas as pd
from pipeline import run_full_pipeline, run_pipeline_from_dataframe
from scoring import calculate_quality_score
from csv_loading import load_csv
from profiling import profile_column
from validity_checks import check_date_validity, check_phone_validity, check_currency_validity

ROOT = Path(__file__).resolve().parents[1] / 'docs/statistics-audit'
# Expected findings are derived from the intentionally edited CSV cells.
EXPECTED = {
 'clean': (100, 'A', []),
 'missing': (62.5, 'C', [('missing','measurement',1,20),('missing','email',2,20)]),
 'duplicates': (85, 'B', [('duplicate',None,3,23),('repeated_identifier','record_id',5,23)]),
 'invalid': (82, 'B', [('invalid_numeric','measurement',1,20),('invalid_email','email',1,20),('format','region',1,20)]),
 'outlier': (100, 'A', [('outlier','measurement',1,20)]),
 'mixed': (38, 'F', [('missing','measurement',1,20),('invalid_numeric','measurement',1,19),('outlier','measurement',1,18),('missing','email',2,20),('invalid_email','email',1,18),('format','region',1,20)]),
 'many_fields': (0, 'F', [('missing',f'field_{i}',1,20) for i in range(7)]),
 'all_missing': (32.5, 'F', [('missing',c,20,20) for c in ['measurement','email','region']]),
}
NULLS = {'', 'na', 'n/a', 'null', 'nan', 'none'}
def quantile(values, q):
 values = sorted(values); pos = (len(values)-1)*q; lo = math.floor(pos); hi = math.ceil(pos)
 return values[lo] + (values[hi]-values[lo])*(pos-lo)

class StatisticsAudit(unittest.TestCase):
 def test_csv_pipeline_and_independent_profiles(self):
  for name,(score,grade,expected) in EXPECTED.items():
   with self.subTest(dataset=name):
    path=ROOT/'fixtures'/f'{name}.csv'
    with path.open(newline='',encoding='utf8') as f:
     reader=csv.DictReader(f); rows=list(reader); fields=reader.fieldnames
    result=run_full_pipeline(path)
    self.assertEqual((result['total_rows'],result['total_columns']), (len(rows),len(fields)))
    self.assertEqual((result['score'],result['grade']), (score,grade))
    self.assertEqual([(i['check'],i['column'],i['count'],i['denominator']) for i in result['issues']],expected)
    self.assertEqual(result['issue_summary'],dict(Counter(i[0] for i in expected)))
    self.assertEqual(len(result['translated_issues']),len(expected))
    self.assertEqual(len(result['recommendations']),len(expected))
    # Frozen pre-Phase-2 evidence remains an independent arithmetic reference.
    # New categories and intentional score-policy changes are verified separately.
    historical=json.loads((ROOT/'results.json').read_text(encoding='utf8'))[name]
    def original_contract(value):
     if isinstance(value,dict):
      return {k:original_contract(v) for k,v in value.items() if k not in {'category','finding_summary','domain_validation','score_policy','score','grade','label','total_penalty','issue_details'}}
     if isinstance(value,list): return [original_contract(v) for v in value]
     return value
    self.assertEqual(original_contract(result),original_contract(historical))
    self.assertEqual(max(0,round(100-result['total_penalty'],1)),score)
    self.assertEqual(result['score_policy']['name'],'quality_errors_weighted_penalty_v2')
    self.assertTrue(all('category' in i for i in result['issues']))
    for item in result['translated_issues']:
     evidence=item['issue_to_review']['evidence']
     original=next(i for i in result['issues'] if i['check']==evidence['issue_type'] and i['column']==evidence['column'])
     self.assertEqual(evidence['affected_records'],original['count'])
     self.assertEqual(evidence['affected_percentage'],original['pct'])
     self.assertEqual(evidence['denominator'],original['denominator'])

    for issue in result['issues']:
     self.assertEqual(issue['pct'],round(100*issue['count']/issue['denominator'],1))
     self.assertEqual(issue['count'],len(set(issue['row_indices'])))
     self.assertTrue(all(0 <= i < len(rows) for i in issue['row_indices']))
    for field in fields:
     present=[r[field] for r in rows if r[field].strip().lower() not in NULLS]
     counts=Counter(present); full=result['column_profiles'][field]['measurements']['full']
     self.assertEqual(full['present_count'],len(present))
     self.assertEqual(full['missing_count'],len(rows)-len(present))
     self.assertEqual(full['missing_percentage'],round(100*(len(rows)-len(present))/len(rows),2))
     self.assertEqual(full['unique_count'],len(counts))
     self.assertEqual(full['blank_count'],sum(r[field].strip()=='' for r in rows))
     self.assertEqual(full['frequency_summary'],{'singleton_values':sum(n==1 for n in counts.values()),'repeated_values':sum(n>1 for n in counts.values())})
     for entry in full['common_values']: self.assertEqual(entry['count'],counts[entry['value']])
     sample=result['column_profiles'][field]['measurements']['sample']
     self.assertEqual((sample['size'],sample['population']),(len(present),len(present)))
     if present:
      self.assertEqual(sample['length'],{'min':min(map(len,present)),'max':max(map(len,present)),'median':statistics.median(map(len,present))})

     self.assertEqual(full['excess_repetitions'],len(present)-len(counts))
     self.assertEqual(full['repeated_occurrences'],sum(n for n in counts.values() if n>1))
     self.assertEqual(full['uniqueness'],len(counts)/max(len(present),1))
     numeric=[]
     for v in present:
      try:
       n=float(v)
       if math.isfinite(n): numeric.append(n)
      except ValueError: pass
     self.assertEqual(full['finite_numeric_ratio'],len(numeric)/max(len(present),1))
     if numeric:
      stats=full['numeric']
      self.assertEqual(stats['distinct_count'],len(set(numeric)))
      self.assertEqual(stats['integer_ratio'],sum(v.is_integer() for v in numeric)/len(numeric))
      if len(numeric)>=3:
       sample_std=statistics.stdev(numeric)
       skew=0 if not sample_std else len(numeric)/((len(numeric)-1)*(len(numeric)-2))*sum(((v-statistics.mean(numeric))/sample_std)**3 for v in numeric)
       self.assertAlmostEqual(stats['skew'],skew)

      for key,value in {'min':min(numeric),'max':max(numeric),'mean':statistics.mean(numeric),'median':statistics.median(numeric),'std':statistics.pstdev(numeric),'q1':quantile(numeric,.25),'q3':quantile(numeric,.75),'finite_count':len(numeric)}.items():
       self.assertAlmostEqual(stats[key],value,msg=f'{name}/{field}/{key}')
    if name in ('outlier','mixed'):
     values=[float(r['measurement']) for r in rows if r['measurement'] not in ('null','oops')]
     q1,q3=quantile(values,.25),quantile(values,.75)
     indices=[i for i,r in enumerate(rows) if r['measurement'] not in ('null','oops') and (float(r['measurement'])<q1-1.5*(q3-q1) or float(r['measurement'])>q3+1.5*(q3-q1))]
     self.assertEqual(next(i for i in result['issues'] if i['check']=='outlier')['row_indices'],indices)
    json.dumps(result,allow_nan=False)

 def test_empty_and_zero_denominators(self):
  for content in (b'',b'a,b\n'):
   with self.assertRaises(ValueError): load_csv(content)
  full=profile_column(pd.Series([],dtype='object'))['full']
  self.assertEqual(full['missing_percentage'],0)
  self.assertEqual(full['finite_numeric_ratio'],0)
  self.assertEqual(calculate_quality_score([],pd.DataFrame())['score'],100)

 def test_scoring_boundaries_and_grades(self):
  df=pd.DataFrame({'a':[1]})
  for pct,penalty in [(0.1,7.5),(1,7.5),(1.1,15),(5,15),(5.1,22.5)]:
   self.assertEqual(calculate_quality_score([{'check':'missing','column':'a','count':1,'pct':pct}],df)['total_penalty'],penalty)
  # Generate exact penalty totals with existing weights, without changing rules.
  for n,score,grade in [(0,100,'A'),(1,90,'A'),(2,80,'B'),(3,70,'C'),(4,60,'C'),(5,50,'D'),(6,40,'D'),(7,30,'F'),(11,0,'F')]:
   issues=[{'check':'duplicate','count':1,'pct':2} for _ in range(n)]
   result=calculate_quality_score(issues,df)
   self.assertEqual((result['score'],result['grade']),(score,grade))
  issues=[{'check':'missing','column':'a','count':1,'pct':5}]*2
  self.assertEqual(calculate_quality_score(issues,df)['total_penalty'],15)

 def test_relationship_arithmetic(self):
  frame=pd.DataFrame({'group':['A']*15+['B']*15, 'category':['X']*15+['Y']*14+['X'], 'a':['']*8+['ok']*22, 'b':['']*9+['ok']*21})
  result=run_pipeline_from_dataframe(frame)
  observations=result['relationships']['observations']
  co=next(r for r in observations if r['kind']=='co_missingness' and set(r['columns'])=={'a','b'})
  self.assertEqual((co['overlap_count'],co['union_count'],co['jaccard']),(8,9,round(8/9,3)))
  group=next(r for r in observations if r['kind']=='missing_concentration' and r['column']=='a' and r['group_column']=='group')
  self.assertEqual((group['missing_count'],group['group_count'],group['group_rate'],group['outside_rate']),(8,15,round(8/15,3),0))
  dep=next(r for r in observations if r['kind']=='categorical_dependency' and r['determinant']=='group' and r['dependent']=='category')
  self.assertEqual((dep['support'],dep['agreement']),(30,round(29/30,3)))
  finding=next(i for i in result['issues'] if i['check']=='relationship_deviation' and i['column']=='category')
  self.assertEqual((finding['count'],finding['denominator'],finding['pct']),(1,30,3.3))

 def test_sample_ratios_and_nonfinite_profile(self):
  profile=profile_column(pd.Series(['01234']*1200))
  self.assertEqual((profile['sample']['size'],profile['sample']['population']),(1000,1200))
  self.assertEqual(profile['sample']['leading_zero_ratio'],1)
  for key in ['email_ratio','phone_ratio','date_parse_ratio','percentage_ratio','prose_ratio','code_ratio']:
   self.assertEqual(profile['sample'][key],0)
  self.assertEqual(profile['sample']['currency_ratio'],1)
  self.assertEqual(profile['sample']['patterns'],[{'value':'9','count':1000}])
  full=profile_column(pd.Series(['1','2','inf','-inf','oops','NA']))['full']
  self.assertEqual((full['numeric_parse_ratio'],full['finite_numeric_ratio']),(4/5,2/5))
  self.assertEqual(full['numeric']['mean'],1.5)
  self.assertEqual(full['numeric']['std'],.5)
  json.dumps(full,allow_nan=False)

 def test_additional_validity_denominators(self):
  df=pd.DataFrame({'date':['2024-01-15','2024-01-16','2024-13-40','NA'], 'phone':['0123456789','+27 82 123 4567','123',''], 'currency':['$12.00','$15.00','bad','null']})
  for fn,col in [(check_date_validity,'date'),(check_phone_validity,'phone'),(check_currency_validity,'currency')]:
   result=fn(df,col)
   self.assertEqual((result['count'],result['pct'],result['row_indices']),(1,33.3,[2]))

if __name__=='__main__': unittest.main()
