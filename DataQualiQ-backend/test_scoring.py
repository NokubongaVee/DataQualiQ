def main():
    # test_scoring.py
    import pandas as pd
    from scoring import calculate_quality_score
    
    # Create sample issues (like what your checks would produce)
    sample_issues = [
        {"check": "missing", "column": "Email", "count": 312, "pct": 3.7},
        {"check": "duplicate", "column": None, "count": 148, "pct": 1.8},
        {"check": "invalid_phone", "column": "Phone", "count": 96, "pct": 1.1},
        {"check": "outlier", "column": "Price", "count": 18, "pct": 0.2},
        {"check": "format", "column": "Signup_date", "count": 45, "pct": 0.5},
    ]
    
    # Sample dataframe with 10,000 rows
    sample_df = pd.DataFrame({"dummy": range(10000)})
    
    # Calculate score
    result = calculate_quality_score(sample_issues, sample_df)
    
    # Print results
    print("=" * 50)
    print("DataQualiQ - Scoring Test")
    print("=" * 50)
    print(f"Score: {result['score']}/100")
    print(f"Grade: {result['grade']} - {result['label']}")
    print(f"Total Penalty: {result['total_penalty']}")
    print(f"Issues Found: {result['issues_found']}")
    print(f"Total Rows: {result['total_rows']}")
    print(f"Total Columns: {result['total_columns']}")
    print("\nIssue Details:")
    print("-" * 50)
    for detail in result['issue_details']:
        print(f"  {detail['type']} ({detail['column']})")
        print(f"    Count: {detail['count']} | Penalty: {detail['penalty']} | Severity: {detail['severity']}")


if __name__ == "__main__":
    main()
