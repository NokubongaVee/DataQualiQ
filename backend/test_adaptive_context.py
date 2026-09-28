
import unittest

import pandas as pd

from dataset_context import infer_dataset_context
from type_inference import infer_all_column_profiles
from translator import translate_all_issues


class AdaptiveContextTests(unittest.TestCase):

    # ---------------------------------------------------------
    # EXISTING DOMAIN TESTS
    # ---------------------------------------------------------

    def test_hr_context_inference(self):
        df = pd.DataFrame(
            {
                "Employee_ID": [101, 102, 103],
                "Employee_Name": ["Alice", "Bob", "Carol"],
                "Department": ["IT", "HR", "Finance"],
                "Salary": [60000, 70000, 80000],
                "Phone": ["555-1234", "555-5678", "555-9876"],
                "Email": [
                    "alice@corp.com",
                    "bob@corp.com",
                    "carol@corp.com",
                ],
                "Hire_Date": [
                    "2021-01-04",
                    "2020-11-02",
                    "2023-02-06",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertIn(
            context["name"],
            {"human_resources", "hr", "people_operations"},
        )
        self.assertGreaterEqual(context["confidence"], 0.5)

    def test_education_context_inference(self):
        df = pd.DataFrame(
            {
                "Student_ID": [1, 2, 3],
                "Student_Name": ["Mpho", "Lerato", "Aisha"],
                "Programme": ["CS", "Math", "Biology"],
                "Mark": [88, 72, 95],
                "Phone": ["081111", "082222", "083333"],
                "Email": [
                    "mpho@mail.com",
                    "lerato@mail.com",
                    "aisha@mail.com",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertIn(
            context["name"],
            {"education", "students", "academic"},
        )
        self.assertGreaterEqual(context["confidence"], 0.5)

    def test_sales_context_inference(self):
        df = pd.DataFrame(
            {
                "Customer_ID": [1, 2, 3],
                "Product": ["Laptop", "Phone", "Tablet"],
                "Quantity": [2, 1, 4],
                "Price": [1200, 850, 500],
                "Order_Date": [
                    "2024-01-02",
                    "2024-02-12",
                    "2024-03-10",
                ],
                "Customer_Phone": [
                    "555-1000",
                    "555-2000",
                    "555-3000",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertIn(
            context["name"],
            {"sales", "commerce", "retail"},
        )
        self.assertGreaterEqual(context["confidence"], 0.5)

    def test_unknown_context_still_returns_generic_value(self):
        df = pd.DataFrame(
            {
                "X1": ["a", "b", "c"],
                "X2": [1, 2, 3],
                "X3": ["x", "y", "z"],
                "X4": [10, 11, 12],
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "unknown")


    # ---------------------------------------------------------
    # EXISTING FLEXIBILITY TESTS
    # ---------------------------------------------------------

    def test_unfamiliar_hr_names_still_infer_hr_context(self):
        df = pd.DataFrame(
            {
                "worker_code": [101, 102, 103],
                "full_name": ["Alice", "Bob", "Carol"],
                "division": ["IT", "Finance", "Operations"],
                "monthly_compensation": [60000, 75000, 82000],
                "contact_number": [
                    "555-1001",
                    "555-1002",
                    "555-1003",
                ],
                "start_dt": [
                    "2021-01-04",
                    "2020-11-02",
                    "2023-02-06",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertIn(
            context["name"],
            {"human_resources", "finance", "unknown"},
        )
        self.assertGreaterEqual(context["confidence"], 0.2)
        self.assertIn("evidence", context)

    def test_unfamiliar_education_and_inventory_names_still_infer_context(self):
        education_df = pd.DataFrame(
            {
                "learner_no": [1, 2, 3],
                "learner_name": ["Mpho", "Lerato", "Aisha"],
                "programme_name": ["CS", "Math", "Biology"],
                "assessment_score": [88, 72, 95],
                "term": ["Term 1", "Term 2", "Term 3"],
                "contact_info": [
                    "mpho@mail.com",
                    "lerato@mail.com",
                    "aisha@mail.com",
                ],
            }
        )

        inventory_df = pd.DataFrame(
            {
                "item_code": ["A1", "A2", "A3"],
                "units_available": [12, 8, 15],
                "unit_cost": [1200, 850, 500],
                "storage_location": ["A-1", "B-2", "C-3"],
                "supplier_ref": ["S-1", "S-2", "S-3"],
                "stock_date": [
                    "2024-01-02",
                    "2024-02-12",
                    "2024-03-10",
                ],
            }
        )

        education_context = infer_dataset_context(education_df)
        inventory_context = infer_dataset_context(inventory_df)

        self.assertIn(
            education_context["name"],
            {"education", "unknown"},
        )
        self.assertIn(
            inventory_context["name"],
            {"inventory", "unknown"},
        )
        self.assertIn("evidence", education_context)
        self.assertIn("evidence", inventory_context)


    # ---------------------------------------------------------
    # COLUMN PROFILE TEST
    # ---------------------------------------------------------

    def test_column_profiles_include_roles_and_confidence(self):
        df = pd.DataFrame(
            {
                "Employee_ID": [1, 2, 3],
                "Salary": [50000, 55000, 60000],
                "Phone": [
                    "555-1111",
                    "555-2222",
                    "555-3333",
                ],
            }
        )

        profiles = infer_all_column_profiles(df)

        self.assertIn(
            profiles["Employee_ID"]["role"],
            {"identifier", "employee_identifier"},
        )
        self.assertIn(
            profiles["Salary"]["role"],
            {"monetary_value", "financial_value"},
        )
        self.assertIn(
            profiles["Phone"]["role"],
            {
                "contact_information",
                "phone",
                "employee_contact",
            },
        )

        self.assertGreaterEqual(
            profiles["Phone"]["confidence"],
            0.0,
        )
        self.assertLessEqual(
            profiles["Phone"]["confidence"],
            1.0,
        )


    # ---------------------------------------------------------
    # NEW REGRESSION TESTS
    # ---------------------------------------------------------

    def test_single_employee_name_column_does_not_dominate_dataset(self):
        """
        Regression test for the main evidence-inflation problem.

        Employee_Name contains several correlated HR signals:
        employee + name + person_name.

        These should NOT be treated as multiple independent
        dataset-level observations.
        """

        df = pd.DataFrame(
            {
                "Employee_Name": [
                    "Alice",
                    "Bob",
                    "Carol",
                    "David",
                ]
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "unknown")
        self.assertLessEqual(context["confidence"], 0.35)


    def test_single_salary_column_does_not_create_high_confidence_hr(self):
        """
        Salary is a useful HR signal, but salary alone does not
        establish that the entire dataset is HR.
        """

        df = pd.DataFrame(
            {
                "Salary": [
                    40000,
                    50000,
                    60000,
                    70000,
                ]
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "unknown")
        self.assertLessEqual(context["confidence"], 0.35)


    def test_generic_dataset_is_unknown(self):
        """
        Generic columns should not create a domain classification.
        """

        df = pd.DataFrame(
            {
                "ID": [1, 2, 3, 4],
                "Name": ["A", "B", "C", "D"],
                "Value": [10, 20, 30, 40],
                "Date": [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                ],
                "Status": [
                    "Active",
                    "Inactive",
                    "Active",
                    "Active",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "unknown")
        self.assertLessEqual(context["confidence"], 0.35)


    def test_multiple_hr_columns_strengthen_hr_context(self):
        """
        Independent HR concepts from different columns should
        strengthen the HR classification.
        """

        df = pd.DataFrame(
            {
                "Employee_Name": [
                    "Alice",
                    "Bob",
                    "Carol",
                    "David",
                ],
                "Department": [
                    "IT",
                    "HR",
                    "Finance",
                    "Operations",
                ],
                "Salary": [
                    60000,
                    70000,
                    80000,
                    75000,
                ],
                "Hire_Date": [
                    "2021-01-04",
                    "2020-11-02",
                    "2023-02-06",
                    "2022-05-10",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "human_resources")
        self.assertGreaterEqual(context["confidence"], 0.5)


    def test_multiple_education_columns_strengthen_education_context(self):
        """
        Student, programme and assessment are separate educational
        concepts and should reinforce each other.
        """

        df = pd.DataFrame(
            {
                "Student_Name": [
                    "Mpho",
                    "Lerato",
                    "Aisha",
                    "John",
                ],
                "Programme": [
                    "Computer Science",
                    "Mathematics",
                    "Biology",
                    "Physics",
                ],
                "Mark": [88, 72, 95, 81],
                "Semester": [
                    "Semester 1",
                    "Semester 1",
                    "Semester 2",
                    "Semester 2",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "education")
        self.assertGreaterEqual(context["confidence"], 0.5)


    def test_multiple_sales_columns_strengthen_sales_context(self):
        """
        Customer, product, quantity, price and order date provide
        several independent sales concepts.
        """

        df = pd.DataFrame(
            {
                "Customer_ID": [1, 2, 3, 4],
                "Product": [
                    "Laptop",
                    "Phone",
                    "Tablet",
                    "Monitor",
                ],
                "Quantity": [2, 1, 4, 3],
                "Price": [1200, 850, 500, 700],
                "Order_Date": [
                    "2024-01-02",
                    "2024-02-12",
                    "2024-03-10",
                    "2024-04-05",
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "sales")
        self.assertGreaterEqual(context["confidence"], 0.5)


    def test_misleading_product_name_does_not_create_hr_person_name(self):
        """
        product_name contains 'name', but it should not be interpreted
        as a person name and should not create HR evidence.
        """

        df = pd.DataFrame(
            {
                "Product_Name": [
                    "Laptop",
                    "Phone",
                    "Tablet",
                    "Monitor",
                ]
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "unknown")
        self.assertLessEqual(context["confidence"], 0.35)


    def test_contact_number_with_numeric_ids_is_not_strong_phone_evidence(self):
        """
        Numeric identifiers named contact_number should not by themselves
        create a strong domain classification.
        """

        df = pd.DataFrame(
            {
                "Contact_Number": [
                    100001,
                    100002,
                    100003,
                    100004,
                ]
            }
        )

        context = infer_dataset_context(df)

        self.assertEqual(context["name"], "unknown")
        self.assertLessEqual(context["confidence"], 0.35)


    def test_small_hr_dataset_is_conservative(self):
        """
        Two HR-looking columns provide some evidence, but a very small
        dataset should not automatically receive high confidence.
        """

        df = pd.DataFrame(
            {
                "Employee_Name": [
                    "Alice",
                    "Bob",
                    "Carol",
                ],
                "Salary": [
                    50000,
                    60000,
                    70000,
                ],
            }
        )

        context = infer_dataset_context(df)

        self.assertIn(
            context["name"],
            {"human_resources", "unknown"},
        )

        self.assertLessEqual(
            context["confidence"],
            0.75,
        )


    def test_conflicting_signals_remain_conservative(self):
        """
        A dataset containing conflicting domain signals should not
        become highly confident merely because several signals exist.
        """

        df = pd.DataFrame(
            {
                "Employee_Name": [
                    "Alice",
                    "Bob",
                    "Carol",
                ],
                "Product": [
                    "Laptop",
                    "Phone",
                    "Tablet",
                ],
                "Salary": [
                    50000,
                    60000,
                    70000,
                ],
                "Student_ID": [1, 2, 3],
            }
        )

        context = infer_dataset_context(df)

        self.assertLessEqual(context["confidence"], 0.75)
        self.assertIn("name", context)
        self.assertIn("evidence", context)


    # ---------------------------------------------------------
    # TRANSLATOR TEST
    # ---------------------------------------------------------

    def test_translator_returns_structured_review_and_recommendation(self):
        issue = {
            "check": "missing",
            "column": "phone",
            "count": 25,
            "pct": 8.3,
            "examples": [None, "", "N/A"],
        }

        translated = translate_all_issues(
            [issue],
            column_names=[
                "Employee_ID",
                "Employee_Name",
                "Phone",
            ],
            dataset_context={
                "name": "human_resources",
                "confidence": 0.92,
            },
        )

        self.assertIn(
            "issue_to_review",
            translated[0],
        )
        self.assertIn(
            "recommendation",
            translated[0],
        )
        self.assertIn(
            "impact",
            translated[0]["issue_to_review"],
        )
        self.assertIn(
            "action",
            translated[0]["recommendation"],
        )


if __name__ == "__main__":
    unittest.main()

