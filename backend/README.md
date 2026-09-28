# DataQualiQ assessment API

The FastAPI backend loads CSV files, profiles columns, selects checks, enriches findings, generates contextual recommendations, and calculates a weighted quality score.

See the [main project README](../README.md) for installation, examples, product screenshots, project progress, and limitations. See [Architecture](../docs/ARCHITECTURE.md) for module responsibilities.

```powershell
py -3.13 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run regression tests with `.\venv\Scripts\python.exe -m unittest discover -v`.

Public `sample_data` files are demonstrations, not independently labelled accuracy benchmarks. The original input is never automatically cleaned or overwritten.
