# scoring.py
import pandas as pd
from typing import List, Dict, Any


def calculate_quality_score(issues: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate overall data quality score using weighted severity approach.
    
    Weights:
    - Missing values: 15 points per column with >5% missing
    - Duplicate rows: 10 points
    - Invalid data (email, date, phone, currency): 8 points each
    - Format inconsistency: 5 points each
    - Outliers: 3 points each
    """
    
    # Define weights
    WEIGHTS = {
        "missing": 15,
        "duplicate": 10,
        "invalid_email": 8,
        "invalid_date": 8,
        "invalid_phone": 8,
        "invalid_currency": 8,
        "invalid_numeric": 5,
        "invalid_text": 5,
        "invalid_categorical": 5,
        "format": 5,
        "outlier": 3,
    }
    
    total_penalty = 0
    issue_details = []
    
    # Track which columns we've already penalized to avoid double-counting
    penalized_columns = {"missing": set(), "format": set()}
    
    for issue in issues:
        check_type = issue["check"]
        column = issue.get("column")
        count = issue["count"]
        if count <= 0:
            continue
        pct = issue.get("pct", 0)
        
        # Get weight for this issue type
        weight = WEIGHTS.get(check_type, 5)
        
        # Apply severity modifier based on percentage of rows affected
        if pct > 5:
            severity_modifier = 1.5  # Severe
        elif pct > 1:
            severity_modifier = 1.0  # Moderate
        else:
            severity_modifier = 0.5  # Minor
        
        # Calculate penalty for this issue
        penalty = weight * severity_modifier
        
        # Avoid double-penalizing the same column for the same issue type
        if check_type in ["missing", "format"]:
            if column in penalized_columns[check_type]:
                penalty = 0
            else:
                penalized_columns[check_type].add(column)
        
        total_penalty += penalty
        
        # Store details for reporting
        issue_details.append({
            "type": check_type,
            "column": column,
            "count": count,
            "pct": pct,
            "penalty": round(penalty, 1),
            "weight": weight,
            "severity": "High" if severity_modifier == 1.5 else "Medium" if severity_modifier == 1.0 else "Low"
        })
    
    # Calculate final score (minimum 0)
    score = max(0, 100 - total_penalty)
    score = round(score, 1)
    
    # Determine grade
    if score >= 90:
        grade = "A"
        label = "Excellent"
    elif score >= 75:
        grade = "B"
        label = "Good"
    elif score >= 60:
        grade = "C"
        label = "Fair"
    elif score >= 40:
        grade = "D"
        label = "Poor"
    else:
        grade = "F"
        label = "Critical"
    
    return {
        "score": score,
        "grade": grade,
        "label": label,
        "total_penalty": round(total_penalty, 1),
        "issue_details": issue_details,
        "issues_found": len(issue_details),
        "total_rows": len(df),
        "total_columns": len(df.columns)
    }


def get_issue_summary_by_type(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count issues by type for dashboard summary cards"""
    summary = {}
    for issue in issues:
        check_type = issue["check"]
        if check_type not in summary:
            summary[check_type] = 0
        summary[check_type] += 1
    return summary