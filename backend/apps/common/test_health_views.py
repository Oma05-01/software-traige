from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase


class HealthEndpointTests(TestCase):

    def test_liveness_does_not_access_database(self):
        with patch(
            "apps.common.views.connection.cursor"
        ) as mock_cursor:
            response = self.client.get("/api/health/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

        mock_cursor.assert_not_called()

    def test_readiness_returns_200_when_database_is_available(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(
            response.json()["services"]["database"],
            "ok",
        )

    def test_readiness_returns_503_when_database_is_unavailable(self):
        with patch(
            "apps.common.views.connection.cursor",
            side_effect=DatabaseError("Database unavailable"),
        ):
            response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")
        self.assertEqual(
            response.json()["services"]["database"],
            "unavailable",
        )

