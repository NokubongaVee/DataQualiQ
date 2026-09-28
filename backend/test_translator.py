def main():
    # test_translator.py
    from translator import translate_all_issues
    
    # Sample issues (like what your checks would produce)
    sample_issues = [
        {"check": "missing", "column": "Email", "count": 312, "pct": 3.7},
        {"check": "duplicate", "column": None, "count": 148, "pct": 1.8},
        {"check": "invalid_phone", "column": "Phone", "count": 96, "pct": 1.1, "examples": ["123", "abc", "0000"]},
        {"check": "outlier", "column": "Price", "count": 18, "pct": 0.2, "examples": ["999999", "0.01", "500000"]},
        {"check": "format", "column": "Signup_date", "count": 45, "pct": 0.5},
        {"check": "invalid_numeric", "column": "Age", "count": 3, "pct": 0.1, "examples": ["-5", "200", "0"]},
        {"check": "invalid_text", "column": "Name", "count": 8, "pct": 0.3, "examples": ["A", "    ", "Th@bo"]},
        {"check": "invalid_categorical", "column": "Gender", "count": 2, "pct": 0.1, "examples": ["X", "M"]},
    ]
    
    # Translate all issues
    translated = translate_all_issues(sample_issues)
    
    print("=" * 70)
    print("PLAIN-LANGUAGE TRANSLATION")
    print("=" * 70)
    
    for structured in translated:
        issue = structured['legacy']
        print(f"\n {issue['title']}" if issue['severity'] == "high" else 
              f"\n {issue['title']}" if issue['severity'] == "medium" else 
              f"\n {issue['title']}")
        print(f"   {issue['description']}")
        print(f"    Suggestion: {issue['suggestion']}")


if __name__ == "__main__":
    main()
