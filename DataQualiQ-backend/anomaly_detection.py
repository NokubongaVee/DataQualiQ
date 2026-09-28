import pandas as pd
import numpy as np


def _check_outliers_iqr(df: pd.DataFrame, col: str) -> dict:
    """
    Detect outliers using the IQR (Interquartile Range) method.
    Used for all dataset sizes; flags candidates for human review.
    A value is flagged if it falls far outside the middle 50% of the data.
    """
    values = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1

    # If the data has no real spread (e.g. every value is identical),
    # there's nothing meaningful to flag as an outlier.
    if iqr == 0 and values.nunique() <= 1:
        return {"check": "outlier", "column": col, "count": 0, "pct": 0, "row_indices": [], "examples": []}

    with np.errstate(over='ignore', invalid='ignore'):
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
    if not np.isfinite(lower_bound) or not np.isfinite(upper_bound):
        return {"check": "outlier", "column": col, "count": 0, "pct": 0,
                "row_indices": [], "examples": []}

    outlier_mask = (values < lower_bound) | (values > upper_bound)
    outlier_rows = values.index[outlier_mask]
    outlier_values = values.loc[outlier_rows].tolist()

    return {
        "check": "outlier", "column": col, "count": int(outlier_mask.sum()),
        "pct": round(100 * outlier_mask.sum() / len(values), 1) if len(values) else 0,
        "row_indices": outlier_rows.tolist(), "examples": outlier_values[:3],
        "denominator": len(values), "review_only": True,
        "statistics": {"q1": float(q1), "q3": float(q3), "iqr": float(iqr),
                       "lower_bound": float(lower_bound), "upper_bound": float(upper_bound),
                       "multiplier": 1.5},
    }


def check_numeric_outliers(df: pd.DataFrame, col: str) -> dict:
    values = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(values) < 5:
        return {"check": "outlier", "column": col, "count": 0, "pct": 0, "row_indices": [], "examples": []}

    # IQR is deterministic and robust to a small number of extreme values,
    # so it remains appropriate as the dataset grows instead of assuming a
    # fixed contamination rate for every numeric column.
    return _check_outliers_iqr(df, col)


def run_anomaly_detection(df: pd.DataFrame, column_profiles: dict) -> list:
    issues = []

    for col, profile in column_profiles.items():
        col_type = profile.get("type", "unknown")
        role = profile.get("role", "unknown")

        # Only detect anomalies in numeric columns.
        if col_type != "numeric":
            continue

        # Do not treat identifiers as statistical outliers.
        if role == "identifier":
            continue

        result = check_numeric_outliers(df, col)

        if result["count"] > 0:
            issues.append(result)

    return issues
