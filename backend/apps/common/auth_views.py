import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


User = get_user_model()


def user_payload(user):
    """Return the minimum staff identity information needed by Next.js."""

    return {
        "id": str(user.pk),
        "username": user.get_username(),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
    }


@never_cache
@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    """
    Initialise the CSRF cookie and return a masked token
    for subsequent state-changing requests.
    """

    return JsonResponse({
        "csrfToken": get_token(request),
    })


@never_cache
@require_POST
@csrf_protect
def staff_login(request):
    """
    Authenticate an active Django staff account and create
    a Django session.
    """

    try:
        payload = json.loads(request.body or b"{}")

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"detail": "Invalid JSON request body."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"detail": "Request body must be a JSON object."},
            status=400,
        )

    identifier = payload.get("username")
    password = payload.get("password")

    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or not isinstance(password, str)
        or not password
    ):
        return JsonResponse(
            {"detail": "Username and password are required."},
            status=400,
        )

    credentials = {
        User.USERNAME_FIELD: identifier.strip(),
        "password": password,
    }

    user = authenticate(
        request,
        **credentials,
    )

    # Use the same response for invalid credentials and
    # accounts that are not permitted to access the staff interface.
    if (
        user is None
        or not user.is_active
        or not user.is_staff
    ):
        return JsonResponse(
            {"detail": "Invalid credentials or insufficient access."},
            status=401,
        )

    login(request, user)

    # Django rotates the CSRF token during login.
    # Return the new token to the frontend.
    return JsonResponse({
        "detail": "Login successful.",
        "user": user_payload(user),
        "csrfToken": get_token(request),
    })


@never_cache
@require_GET
def staff_session(request):
    """Return the current authenticated staff user."""

    user = request.user

    if (
        not user.is_authenticated
        or not user.is_active
        or not user.is_staff
    ):
        return JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    return JsonResponse({
        "authenticated": True,
        "user": user_payload(user),
    })


@never_cache
@require_POST
@csrf_protect
def staff_logout(request):
    """Destroy the current Django session."""

    user = request.user

    if not user.is_authenticated:
        return JsonResponse(
            {"detail": "No active session."},
            status=401,
        )

    logout(request)

    return JsonResponse({
        "detail": "Logout successful.",
        "csrfToken": get_token(request),
    })