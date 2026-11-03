from django.contrib import admin
from django.urls import include, path
from apps.common import auth_views


urlpatterns = [
    path("admin/", admin.site.urls),

    # API endpoints
    path("api/", include("apps.common.urls")),
    path("api/auth/csrf/", auth_views.csrf_token, name="api-csrf"),
    path("api/auth/login/", auth_views.staff_login, name="api-login"),
    path("api/auth/me/", auth_views.staff_session, name="api-session"),
    path("api/auth/logout/", auth_views.staff_logout, name="api-logout"),
     # Ticket management
    path("api/tickets/", include("apps.tickets.urls")),

    path("api/reviews/", include("apps.reviews.urls")),

    path(
        "api/integrations/",
        include("apps.integrations.urls"),
    ),
    path(
        "api/workflows/",
        include("apps.workflow.urls"),
    ),
]