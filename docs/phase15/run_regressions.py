"""Run the complete existing suites and save actual exit status/output."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parents[2]
output = Path(__file__).resolve().parent
backend = root / 'backend'
frontend = root / 'frontend'
env = {**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
tasks = [
 ('backend_tests', [str(backend / 'venv/Scripts/python.exe'), '-B', '-m', 'unittest', 'discover', '-q'], backend),
 ('backend_dependencies', [str(backend / 'venv/Scripts/python.exe'), '-m', 'pip', 'check'], backend),
 ('active_environment_dependencies', [str(root / '.venv/Scripts/python.exe'), '-m', 'pip', 'check'], root),
 ('frontend_tests', ['powershell', '-NoProfile', '-Command', 'npm.cmd test'], frontend),
 ('lint', ['powershell', '-NoProfile', '-Command', 'npm.cmd run lint'], frontend),
 ('production_build', ['powershell', '-NoProfile', '-Command', 'npm.cmd run build'], frontend),
]
def run(task):
 name, command, cwd = task
 result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
 (output / (name + '.log')).write_text(result.stdout, encoding='utf-8')
 return {'name': name, 'input': 'Existing full suite or dependency check', 'expected': 'Exit status 0', 'actual': {'exit_code': result.returncode, 'log': name + '.log'}, 'passed': result.returncode == 0}
with ThreadPoolExecutor(max_workers=6) as pool:
 results = list(pool.map(run, tasks))
(output / 'regression_results.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results))
raise SystemExit(0 if all(item['passed'] for item in results) else 1)
