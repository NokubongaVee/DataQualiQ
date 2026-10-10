# main.py
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import json
from typing import Annotated
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from csv_loading import load_csv
from pipeline import run_pipeline_from_dataframe, run_full_pipeline
from domains.network.schema import NetworkSchema

app = FastAPI(
    title="DataQualiQ API",
    description="Intelligent Data Quality Assessment System",
    version="1.0.0"
)

# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # React dev server
        "http://localhost:5174",  # React dev server (alternative port)
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "DataQualiQ API is running",
        "status": "online",
        "endpoints": {
            "/": "GET - API status",
            "/assess": "POST - Upload CSV for assessment",
            "/predict-network": "POST - Predict compatible network CSV using saved artifacts",
            "/analyze-network": "POST - Combine network quality, prediction and input reliability",
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "DataQualiQ"}


MAX_SIZE = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


def _predict_contents(contents, offset, limit):
    from ml.prediction import PredictionError, predict_network_traffic
    try:
        dataframe = load_csv(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={'code': 'invalid_csv', 'message': str(exc)}) from exc
    try:
        return predict_network_traffic(dataframe, offset=offset, limit=limit)
    except PredictionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc


def _analyze_contents(contents, filename, offset, limit):
    from ml.combined_analysis import analyze_network
    from ml.analysis_response import format_combined_api_response
    from ml.prediction import PredictionError
    try:
        dataframe = load_csv(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={'code': 'invalid_csv', 'message': str(exc)}) from exc
    try:
        return format_combined_api_response(analyze_network(dataframe, filename, offset=offset, limit=limit))
    except PredictionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc


@app.post('/analyze-network')
async def analyze_network_csv(file: UploadFile = File(...),
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=0, le=1000)] = 100):
    try:
        if not file.filename or not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail={'code': 'invalid_file_type', 'message': 'Only CSV files are supported. Please upload a .csv file.'})
        contents = await file.read(MAX_SIZE + 1)
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=400, detail={'code': 'file_too_large', 'message': 'File size exceeds 50MB limit.'})
        result = await run_in_threadpool(_analyze_contents, contents, file.filename, offset, limit)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Combined network analysis failed')
        raise HTTPException(status_code=500, detail={'code': 'analysis_failed', 'message': 'Could not complete combined network analysis. Please try again.'})
    finally:
        await file.close()


@app.post('/predict-network')
async def predict_network_csv(file: UploadFile = File(...),
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=0, le=1000)] = 100):
    try:
        if not file.filename or not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail='Only CSV files are supported. Please upload a .csv file.')
        contents = await file.read(MAX_SIZE + 1)
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=400, detail='File size exceeds 50MB limit.')
        result = await run_in_threadpool(_predict_contents, contents, offset, limit)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Network CSV prediction failed')
        raise HTTPException(status_code=500, detail='Could not complete network prediction. Please try again.')
    finally:
        await file.close()


def _assess_contents(contents, filename, network_schema=None):
    try:
        df = load_csv(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run_pipeline_from_dataframe(df, filename=filename, network_schema=network_schema)


@app.post("/assess")
async def assess_csv(file: UploadFile = File(...), network_schema: Annotated[str | None, Form()] = None):
    try:
        if not file.filename or not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported. Please upload a .csv file.")
        contents = await file.read(MAX_SIZE + 1)
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="File size exceeds 50MB limit.")
        schema = None
        if network_schema is not None:
            try:
                schema = NetworkSchema.from_dict(json.loads(network_schema))
            except (ValueError, TypeError, AttributeError) as exc:
                raise HTTPException(status_code=400, detail='Invalid network schema configuration.') from exc
        result = await run_in_threadpool(_assess_contents, contents, file.filename, schema)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("CSV assessment failed")
        raise HTTPException(status_code=500, detail="Could not complete the assessment. Please try again.")
    finally:
        await file.close()


@app.post("/assess-with-sample")
def assess_with_sample():
    try:
        result = run_full_pipeline(Path(__file__).parent / "sample_data" / "customers_raw.csv")
        return JSONResponse(content=result)
    except Exception:
        logger.exception("Sample assessment failed")
        raise HTTPException(status_code=500, detail="Could not assess the sample file.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
