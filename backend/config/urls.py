from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    # API endpoints
    path("api/", include("apps.common.urls")),

     # Ticket management
    path("api/tickets/", include("apps.tickets.urls")),

    path("api/reviews/", include("apps.reviews.urls")),
]