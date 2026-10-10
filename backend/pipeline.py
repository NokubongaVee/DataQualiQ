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
from finding_categories import classify_findings, category_summary
from domains.network.schema import apply_schema_profiles
from domains.network.validators import validate_network

logger = logging.getLogger(__name__)


def _run_pipeline_on_dataframe(df: pd.DataFrame, filename: str, network_schema=None) -> dict:
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
    if network_schema is not None:
        apply_schema_profiles(column_profiles, network_schema)
    column_types = {col: profile["type"] for col, profile in column_profiles.items()}

    dataset_context = infer_dataset_context(df, column_profiles)
    if network_schema is not None:
        dataset_context = {'name': 'network_traffic', 'confidence': 1.0,
                           'evidence': ['Explicit network schema: ' + network_schema.name],
                           'limitations': ['Configured domain; verify schema semantics against the exporter.']}

    all_issues = run_selected_checks(df, column_profiles)
    relationship_frame = df if network_schema is None else df.drop(columns=list(network_schema.protected_fields), errors='ignore')
    relationship_profiles = {col: column_profiles[col] for col in relationship_frame.columns}
    relationship_issues, relationships = analyse_relationships(relationship_frame, relationship_profiles)
    all_issues = enrich_findings(df, all_issues + relationship_issues, column_profiles, relationships)
    all_issues = add_contextual_guidance(df, all_issues, column_profiles, dataset_context)
    domain_warnings = []
    if network_schema is not None:
        domain_issues, domain_warnings = validate_network(df, network_schema)
        for issue in domain_issues:
            issue.update(id=f'finding-{len(all_issues) + 1}', priority='high', priority_score=.8)
            issue['evidence'] = {'denominator': issue['denominator'], 'population': 'schema-assessed records',
                'row_indices': issue['row_indices'], 'examples': issue.get('examples', []),
                'observations': [issue['reason']], 'candidate': False,
                'potential_impact': ['This field violates the supplied structural schema.'],
                'review_questions': ['Verify the original source and schema. Preserve raw values; use an explicit preprocessing policy to mark invalid features as unknown. Never infer replacement labels.'],
                'limitations': ['Validity depends on the supplied schema matching the exporter.'],
                'priority_reason': 'Explicit schema violation; priority is separate from the heuristic score.'}
            all_issues.append(issue)
    all_issues = classify_findings(all_issues)
    score_result = calculate_quality_score(all_issues, df)

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
        "score_policy": {"name": "quality_errors_weighted_penalty_v2", "heuristic": True,
                         "description": "Heuristic score, not a percentage of correct data. Analytical anomalies and uncertain semantic/category candidates do not reduce it."},
        "finding_summary": category_summary(all_issues),
        "domain_validation": {"enabled": network_schema is not None,
                              "schema": network_schema.to_dict() if network_schema else None,
                              "warnings": domain_warnings},
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


def run_full_pipeline(file_path: str, network_schema=None) -> dict:
    """Run all checks on a CSV file and return complete results."""
    path = Path(file_path)
    df = load_csv(path.read_bytes())
    filename = path.name
    return _run_pipeline_on_dataframe(df, filename, network_schema)


def run_pipeline_from_dataframe(df: pd.DataFrame, filename: str = "uploaded.csv", network_schema=None) -> dict:
    """Run the pipeline directly on a DataFrame (for API use)."""
    return _run_pipeline_on_dataframe(df, filename, network_schema)
