def main():
    # test_validity_enhanced.py
    import pandas as pd
    from validity_checks import run_validity_checks
    from type_inference import infer_all_column_types
    
    # Create test data with various issues
    test_data = {
        "Name": ["Thabo", "A", "John123", "    ", "Valid Name", "Th@bo"],
        "Age": [25, -5, 150, 30, 1000, 28],
        "Email": ["thabo@mail.com", "invalid", "test@mail", "valid@mail.com", "", "missing"],
        "Gender": ["Male", "Female", "M", "F", "Male", "Maleee"],
        "Siblings": [2, 0, -1, 100, 1, 3],
    }
    
    df = pd.DataFrame(test_data)
    
    # Infer column types
    column_types = infer_all_column_types(df)
    print("Detected Column Types:")
    for col, dtype in column_types.items():
        print(f"  {col}: {dtype}")
    
    # Run validity checks
    issues = run_validity_checks(df, column_types)
    
    print("\n" + "=" * 50)
    print("VALIDITY ISSUES FOUND:")
    print("=" * 50)
    
    for issue in issues:
        print(f"\n{issue['check'].upper()} in column '{issue['column']}'")
        print(f"  Count: {issue['count']}")
        print(f"  Percentage: {issue['pct']}%")
        print(f"  Examples: {issue['examples']}")


if __name__ == "__main__":
    main()
