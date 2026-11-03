import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


User = get_user_model()


class StaffAuthenticationTests(TestCase):

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

        self.staff_user = User.objects.create_user(
            username="staff-reviewer",
            password="TestPassword123!",
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular-user",
            password="TestPassword123!",
            is_staff=False,
        )

        self.origin = "http://localhost:3000"

    def obtain_csrf_token(self):
        response = self.client.get("/api/auth/csrf/")

        self.assertEqual(response.status_code, 200)

        return response.json()["csrfToken"]

    def login_staff(self):
        token = self.obtain_csrf_token()

        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({
                "username": "staff-reviewer",
                "password": "TestPassword123!",
            }),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        return response

    def test_csrf_endpoint_returns_token(self):
        response = self.client.get("/api/auth/csrf/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrfToken", response.json())
        self.assertIn("csrftoken", response.cookies)

    def test_login_requires_csrf_token(self):
        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({
                "username": "staff-reviewer",
                "password": "TestPassword123!",
            }),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
        )

        self.assertEqual(response.status_code, 403)

    def test_staff_can_log_in(self):
        response = self.login_staff()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["user"]["is_staff"])

        self.assertIn("csrfToken", response.json())

    def test_regular_user_cannot_log_in(self):
        token = self.obtain_csrf_token()

        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({
                "username": "regular-user",
                "password": "TestPassword123!",
            }),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 401)

    def test_invalid_credentials_are_rejected(self):
        token = self.obtain_csrf_token()

        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({
                "username": "staff-reviewer",
                "password": "wrong-password",
            }),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 401)

    def test_authenticated_staff_can_check_session(self):
        self.login_staff()

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])

        self.assertEqual(
            response.json()["user"]["username"],
            "staff-reviewer",
        )

    def test_unauthenticated_user_cannot_check_session(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 401)

    def test_staff_can_log_out(self):
        login_response = self.login_staff()

        token = login_response.json()["csrfToken"]

        response = self.client.post(
            "/api/auth/logout/",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)

        session_response = self.client.get("/api/auth/me/")

        self.assertEqual(session_response.status_code, 401)

    def test_malformed_json_is_rejected(self):
        token = self.obtain_csrf_token()

        response = self.client.post(
            "/api/auth/login/",
            data="{invalid json",
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_credentials_are_rejected(self):
        token = self.obtain_csrf_token()

        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({
                "username": "staff-reviewer",
            }),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 400)