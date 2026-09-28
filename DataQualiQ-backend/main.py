# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from csv_loading import load_csv
from pipeline import run_pipeline_from_dataframe, run_full_pipeline

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
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "DataQualiQ"}


MAX_SIZE = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


def _assess_contents(contents, filename):
    try:
        df = load_csv(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run_pipeline_from_dataframe(df, filename=filename)


@app.post("/assess")
async def assess_csv(file: UploadFile = File(...)):
    try:
        if not file.filename or not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported. Please upload a .csv file.")
        contents = await file.read(MAX_SIZE + 1)
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="File size exceeds 50MB limit.")
        result = await run_in_threadpool(_assess_contents, contents, file.filename)
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