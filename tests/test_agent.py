import json
import unittest
from unittest.mock import Mock, patch

from agent import CATEGORIES, answer, load_data


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_data()

    def test_loads_cleaned_dataset_and_nulls_as_missing(self):
        self.assertEqual(len(self.rows), 300)
        self.assertIsNone(self.rows[2]["Education_Level"])
        self.assertEqual(self.rows[0]["AI_Usage_Hours_Per_Day"], 2.0)

    def test_average_productivity(self):
        result = answer("What is the average productivity score?", self.rows)
        self.assertIn("Productivity score:", result["summary"])
        self.assertEqual(result["available"], 300)
        self.assertEqual(result["rows"][0][2], 284)

    def test_grouped_comparison_normalizes_categories(self):
        result = answer("Compare time saved by user type", self.rows)
        self.assertEqual(result["columns"][0], "User type")
        self.assertEqual({row[0] for row in result["rows"]}, {"Student", "Professional"})

    def test_popular_tools_are_normalized(self):
        result = answer("Which AI tools are most popular?", self.rows)
        self.assertEqual(result["columns"][0], "AI tool")
        self.assertEqual(result["rows"][0][0], "ChatGPT")

    def test_spanish_group_query(self):
        result = answer("¿Cuál es la satisfacción promedio por país?", self.rows)
        self.assertEqual(result["columns"][0], "Country")
        self.assertGreater(len(result["rows"]), 1)

    def test_unsupported_question_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "couldn't identify a measure"):
            answer("Tell me something interesting", self.rows)

    @patch("agent.build_opener")
    def test_local_model_plan_is_validated_and_calculated_from_csv(self, build_opener):
        filters = {column: "" for column in CATEGORIES}
        plan = {
            "metric": "Productivity_Score",
            "aggregation": "average",
            "group_by": "User_Type",
            "filters": filters,
        }
        response = Mock()
        response.read.return_value = json.dumps({
            "choices": [{"message": {"content": json.dumps(plan)}}],
        }).encode()
        build_opener.return_value.open.return_value.__enter__.return_value = response

        result = answer("Compare average productivity by user type", self.rows, "local-test-model")

        self.assertIn("Local LLM", result["mode"])
        self.assertEqual(result["columns"][0], "User type")
        self.assertEqual({row[0] for row in result["rows"]}, {"Student", "Professional"})

    @patch("agent.build_opener")
    def test_model_cannot_filter_on_values_outside_the_dataset(self, build_opener):
        filters = {column: "" for column in CATEGORIES}
        filters["Country"] = "Atlantis"
        plan = {
            "metric": "Productivity_Score",
            "aggregation": "average",
            "group_by": "",
            "filters": filters,
        }
        response = Mock()
        response.read.return_value = json.dumps({
            "choices": [{"message": {"content": json.dumps(plan)}}],
        }).encode()
        build_opener.return_value.open.return_value.__enter__.return_value = response

        with self.assertRaisesRegex(ValueError, "outside the dataset"):
            answer("Average productivity in Atlantis", self.rows, "local-test-model")


if __name__ == "__main__":
    unittest.main()
