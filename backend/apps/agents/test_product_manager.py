from django.test import SimpleTestCase

from apps.agents.implementations.product_manager import (
    _validate_assessment,
)


class ProductManagerAssessmentValidationTests(SimpleTestCase):

    def make_assessment(self, **overrides):
        assessment = {
            "problem_statement": (
                "The submission does not establish "
                "a specific user problem."
            ),
            "requested_capability": (
                "The requested functionality is unclear."
            ),
            "user_value": (
                "Potential user value cannot yet be assessed."
            ),
            "proposed_scope": (
                "Scope cannot be determined until "
                "the request is clarified."
            ),
            "acceptance_criteria": "",
            "considerations": "",
            "open_questions": (
                "What functionality are you requesting?"
            ),
            "assessment_confidence": "low",
        }

        assessment.update(overrides)
        return assessment

    def test_low_confidence_allows_empty_acceptance_criteria(self):
        result = _validate_assessment(
            self.make_assessment()
        )

        self.assertEqual(
            result["assessment_confidence"],
            "low",
        )

        self.assertEqual(
            result["acceptance_criteria"],
            [],
        )

        self.assertTrue(result["open_questions"])

    def test_low_confidence_adds_question_when_missing(self):
        result = _validate_assessment(
            self.make_assessment(open_questions="")
        )

        self.assertTrue(result["open_questions"])

    def test_medium_confidence_requires_acceptance_criteria(self):
        with self.assertRaises(ValueError):
            _validate_assessment(
                self.make_assessment(
                    assessment_confidence="medium",
                    acceptance_criteria="",
                )
            )

    def test_high_confidence_requires_acceptance_criteria(self):
        with self.assertRaises(ValueError):
            _validate_assessment(
                self.make_assessment(
                    assessment_confidence="high",
                    acceptance_criteria="",
                )
            )

    def test_low_confidence_can_include_acceptance_criteria(self):
        result = _validate_assessment(
            self.make_assessment(
                acceptance_criteria=(
                    "Users can export reports as CSV."
                )
            )
        )

        self.assertEqual(
            result["acceptance_criteria"],
            ["Users can export reports as CSV."],
        )