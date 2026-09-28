def main():
    # test_pipeline.py
    from pipeline import run_full_pipeline
    import json
    
    # Run pipeline on your sample data
    result = run_full_pipeline("sample_data/customers_raw.csv")
    
    print("\n" + "=" * 70)
    print("PIPELINE RESULTS")
    print("=" * 70)
    
    print(f"\n Overall Score: {result['score']}/100")
    print(f"   Grade: {result['grade']} - {result['label']}")
    print(f"   Penalty: {result['total_penalty']}")
    print(f"\n File: {result['filename']}")
    print(f"   Rows: {result['total_rows']}")
    print(f"   Columns: {result['total_columns']}")
    
    print("\n Column Types:")
    for col, col_type in result['column_types'].items():
        print(f"   {col}: {col_type}")
    
    print("\n Issue Summary:")
    for issue_type, count in result['issue_summary'].items():
        print(f"   {issue_type}: {count}")
    
    print("\n" + "=" * 70)
    print("PLAIN-LANGUAGE ISSUES")
    print("=" * 70)
    
    for i, issue in enumerate(result['translated_issues'], 1):
        review = issue.get("issue_to_review", {})
        recommendation = issue.get("recommendation", {})
    
        severity = review.get("severity", "medium").capitalize()
    
        severity_icon = (
            "" if severity == "High"
            else "" if severity == "Medium"
            else ""
        )
    
        title = review.get("title", "Data quality issue")
        description = review.get("description", "No description available.")
        suggestion = recommendation.get(
            "action",
            "No recommendation available."
        )
    
        print(f"\n{i}. {severity_icon} {title}")
        print(f"   {description}")
        print(f"    {suggestion}")
    
    print("\n" + "=" * 70)
    print(" Pipeline test complete!")


if __name__ == "__main__":
    main()
