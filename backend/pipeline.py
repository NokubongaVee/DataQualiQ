# pipeline.py
import logging
from pathlib import Path
import pandas as pd
from csv_loading import load_csv

from type_inference import infer_all_column_profiles
from dataset_context import infer_dataset_context
from check_selection import run_selected_checks
from relationships import analyse_relationships
from finding_evidence import enrich_findings
from contextual_guidance import add_contextual_guidance
from scoring import calculate_quality_score, get_issue_summary_by_type
from translator import translate_all_issues

logger = logging.getLogger(__name__)


def _run_pipeline_on_dataframe(df: pd.DataFrame, filename: str) -> dict:
    """Run all existing checks on an already-loaded DataFrame."""
    if df.empty:
        raise ValueError("The dataset has no data rows or columns.")
    if not df.columns.is_unique:
        raise ValueError("Column names must be unique.")
    df = df.copy()
    df.columns = df.columns.map(str)
    if not df.columns.is_unique:
        raise ValueError("Column names must be unique as strings.")
    df = df.reset_index(drop=True)

    column_profiles = infer_all_column_profiles(df)
    column_types = {col: profile["type"] for col, profile in column_profiles.items()}

    dataset_context = infer_dataset_context(df, column_profiles)

    all_issues = run_selected_checks(df, column_profiles)
    relationship_issues, relationships = analyse_relationships(df, column_profiles)
    all_issues = enrich_findings(df, all_issues + relationship_issues, column_profiles, relationships)
    all_issues = add_contextual_guidance(df, all_issues, column_profiles, dataset_context)
    # New semantic/relationship review candidates do not silently acquire the
    # legacy scorer's default error penalty. Existing scored check types retain
    # their original formula, including historical IQR penalties.
    scored = [i for i in all_issues if i['check'] not in {
        'header_conflict', 'repeated_identifier', 'relationship_deviation',
        'pattern_deviation', 'ambiguous_date'}]
    score_result = calculate_quality_score(scored, df)

    translated_issues = translate_all_issues(
        all_issues,
        column_names=list(df.columns),
        dataset_context=dataset_context,
        column_profiles=column_profiles,
    )

    issues_to_review = [
        {
            "title": item["issue_to_review"]["title"],
            "description": item["legacy"]["description"],
            "impact": item["issue_to_review"]["impact"],
            "severity": item["issue_to_review"]["severity"],
            "evidence": item["issue_to_review"]["evidence"],
        }
        for item in translated_issues
    ]

    recommendations = [
        {
            "title": item["recommendation"]["title"],
            "action": item["recommendation"]["action"],
            "reason": item["recommendation"]["reason"],
            "priority": item["recommendation"]["priority"],
        }
        for item in translated_issues
    ]

    result = {
        "filename": filename,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "column_profiles": column_profiles,
        "column_types": column_types,
        "dataset_context": dataset_context,
        "relationships": relationships,
        "score_policy": {"name": "legacy_weighted_penalty", "heuristic": True,
                         "description": "Heuristic score, not a percentage of correct data. New relationship and semantic review candidates do not reduce it."},
        "issues": all_issues,
        "translated_issues": translated_issues,
        "issues_to_review": issues_to_review,
        "recommendations": recommendations,
        "issue_summary": get_issue_summary_by_type(all_issues),
        "score": score_result["score"],
        "grade": score_result["grade"],
        "label": score_result["label"],
        "total_penalty": score_result["total_penalty"],
        "issue_details": score_result["issue_details"],
    }

    logger.info("Assessment complete: rows=%s columns=%s issues=%s", len(df), len(df.columns), len(all_issues))
    return result


def run_full_pipeline(file_path: str) -> dict:
    """Run all checks on a CSV file and return complete results."""
    path = Path(file_path)
    df = load_csv(path.read_bytes())
    filename = path.name
    return _run_pipeline_on_dataframe(df, filename)


def run_pipeline_from_dataframe(df: pd.DataFrame, filename: str = "uploaded.csv") -> dict:
    """Run the pipeline directly on a DataFrame (for API use)."""
    return _run_pipeline_on_dataframe(df, filename)
