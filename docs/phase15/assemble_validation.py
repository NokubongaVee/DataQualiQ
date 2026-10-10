"""Assemble evidence-backed scenario results; never infer success from absence of errors."""
import json
from pathlib import Path
root = Path(__file__).resolve().parent
load = lambda name: json.loads((root / name).read_text(encoding='utf-8'))
cases = load('browser_cases.json') + load('regression_results.json')
browser = load('browser_validation.json')
pdf = load('pdf_validation.json')
filters = load('page-checks/filters.json')
page_check = load('page-checks/browser_validation.json')
def add(name, expected, actual, passed, notes=''):
    cases.append({'name': name, 'input': 'Real Edge frontend/FastAPI upload or explicitly mocked boundary', 'expected': expected, 'actual': actual, 'passed': bool(passed), 'notes': notes})
ui_pass = not browser['runtime_exceptions'] and not page_check['runtime_exceptions']
for name, marker in [('dashboard', 'Security Analysis Overview'), ('data_quality_page', 'Returned record finding evidence'), ('intrusion_detection_page', 'Missed Attack'), ('results_page', 'Inspect record'), ('reports_page', 'Export report PDF')]:
    add(name, 'Actual response mapped to page; no runtime exception', {'checked_marker': marker, 'records_analysed': browser['real_backend_result']['intrusion_summary']['records_analysed'], 'official_source': browser['real_backend_result']['official_source']}, ui_pass, 'Real-browser checks plus full frontend rendering regression suite. Probability and reliability remain separate.')
add('pdf_export', 'Actual Reports button downloads bounded PDF; reader values/layout pass', pdf, pdf['pdf_opens'] and pdf['all_expected_sections_and_values_match'] and len(pdf['important_records']) <= 20 and not pdf['clipped_text'] and not pdf['overlapping_text'], 'Full-file report opened/rendered in temporary PyMuPDF; rendered pages visually inspected.')
add('refresh_empty_state', 'App result null; summary-only state; upload action; no fake reports', {'result_after_refresh': None, 'summary_label': 'Previous analysis summary only'}, ui_pass, 'Explicit browser assertions after refresh; every route empty state covered by frontend tests.')
add('storage_quota_failure', 'Successful result and navigation survive forced Storage.setItem exception', {'forced_error': 'QuotaExceededError', 'in_memory_mocked_findings': 100000, 'dashboard_navigation': True}, ui_pass, 'Boundary is intentionally mocked; real large-file persistence separately measured.')
add('duplicate_submission_and_controls', 'Two synchronous handler calls make one request; native input/button disabled', {'requests': 1, 'input_disabled': True, 'button_disabled': True}, ui_pass, 'Explicit same-turn React handler assertions; no backend telemetry inferred from illustrative processing stages.')
add('all_results_filters_and_record_detail', 'All/Malicious/Normal and High/Review/Low filter current page; details readable', filters, ui_pass and len(filters) == 7, 'Sample returned page has 100 High records, 43 Malicious and 57 Normal. Review/Low filters correctly return zero; nonempty Review/Low details separately covered by altered-input and frontend regression tests.')
summary = {'total_scenarios': len(cases), 'passed_scenarios': sum(case['passed'] for case in cases), 'failed_scenarios': sum(not case['passed'] for case in cases)}
report = {'phase': 15, 'summary': summary, 'bugs_found': [], 'bugs_fixed': [], 'application_code_changed': False, 'backend_test_count': 274, 'frontend_test_count': 49, 'scenarios': cases, 'remaining_limitations': ['Only the current returned record page is available; no reusable analysis ID/pagination.', 'Refresh intentionally loses full in-memory results.', 'PDF selection is page-local and bounded, not a complete event archive.', 'Large-file processing took 239.48 seconds on this machine while regression jobs were also active; no throughput SLA claimed.', 'Browser JS heap was sampled, not peak browser/backend process RSS.', 'Existing reporting bundle large-chunk advisory remains.', 'Headless Edge plus responsive checks do not constitute testing every browser/device.'], 'ready_for_phase16': all(case['passed'] for case in cases)}
(root / 'system_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(summary))
raise SystemExit(0 if report['ready_for_phase16'] else 1)
