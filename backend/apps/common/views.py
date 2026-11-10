from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def liveness_check(request):
    """
    Check whether the Django application is responding.

    This endpoint intentionally does not check external dependencies.
    """

    return JsonResponse(
        {
            "status": "ok",
            "services": {
                "api": "ok",
            },
        },
        status=200,
    )


@require_GET
def health_check(request):
    """
    Check whether the application can access its database.

    This endpoint is intended for Kubernetes readiness checks.
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

    except DatabaseError:
        return JsonResponse(
            {
                "status": "degraded",
                "services": {
                    "api": "ok",
                    "database": "unavailable",
                },
            },
            status=503,
        )

    return JsonResponse(
        {
            "status": "ok",
            "services": {
                "api": "ok",
                "database": "ok",
            },
        },
        status=200,
    )
