"""Validate the final combined HTTP contract on a real, unlabeled sample."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import urlopen, Request

from csv_loading import load_csv


def main():
    root = Path(__file__).resolve().parents[2]
    backend = root / 'backend'
    metadata = json.loads((backend / 'models/model_metadata.json').read_text(encoding='utf-8'))
    frame = load_csv((root / 'data/UNSW_NB15_testing-set.csv').read_bytes()).iloc[:1000].loc[:, metadata['features']['required_features']].copy()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    # Fit methods are forbidden in the actual API process, not just the client.
    bootstrap = (
        'from sklearn.ensemble import RandomForestClassifier; '
        'from ml.preprocessing import NetworkMLPreprocessor; '
        'from unittest.mock import Mock; '
        'deny=Mock(side_effect=AssertionError("No fitting during inference")); '
        'RandomForestClassifier.fit=deny; NetworkMLPreprocessor.fit=deny; '
        'NetworkMLPreprocessor.fit_transform=deny; '
        f'import uvicorn; uvicorn.run("main:app",host="127.0.0.1",port={port},log_level="warning")'
    )
    environment = {**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen([sys.executable, '-B', '-c', bootstrap], cwd=backend,
            stdout=log, stderr=log, env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        try:
            for _ in range(200):
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health', timeout=1):
                        break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError('Functional API process exited before startup.')
                    time.sleep(.1)
            else:
                raise RuntimeError('Functional API startup timed out.')
            contents = frame.to_csv(index=False).encode()
            body = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="network_sample.csv"\r\nContent-Type: text/csv\r\n\r\n' + contents + b'\r\n--boundary--\r\n'
            request = Request(f'http://127.0.0.1:{port}/analyze-network?offset=0&limit=10', data=body,
                headers={'Content-Type': 'multipart/form-data; boundary=boundary'})
            try:
                with urlopen(request, timeout=120) as response:
                    raw = response.read()
                    result = json.loads(raw)
            except HTTPError as exc:
                raise RuntimeError('Functional API request failed: ' + exc.read().decode()) from exc
            expected = {'data_quality', 'intrusion_summary', 'model_performance', 'reliability_summary', 'records', 'pagination', 'recommendations'}
            if not expected.issubset(result):
                raise ValueError('Final API response sections are missing.')
            for metric in ['accuracy', 'precision', 'recall', 'f1']:
                if result['model_performance'][metric] != metadata['phase5_evaluation']['metrics'][metric]:
                    raise ValueError('API metrics differ from saved official evaluation.')
            if result['model_performance']['is_current_upload_metric']:
                raise ValueError('Official metrics incorrectly attributed to upload.')
            report = {'validation': {'input': 'First 1000 official testing rows; predictive projection only, no labels',
                'actual_http_endpoint': '/analyze-network?offset=0&limit=10',
                'fit_methods_forbidden_in_api_process': True, 'response_bytes': len(raw)}, 'response': result}
            output = root / 'docs/phase9/functional_validation.json'
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
            print(json.dumps({'intrusion_summary': result['intrusion_summary'],
                'quality_score': result['data_quality']['score'],
                'reliability_summary': result['reliability_summary'],
                'page_size': len(result['records']), 'recommendation_count': len(result['recommendations']),
                'response_bytes': len(raw)}), flush=True)
            print('Report: ' + str(output), flush=True)
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
