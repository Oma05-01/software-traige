from django.urls import path

from apps.reviews.views import (
    ApproveReviewRequestView,
    RejectReviewRequestView,
    ReviewProposalUpdateView,
    ReviewRequestDetailView,
    ReviewRequestListView,
)


app_name = "reviews"

urlpatterns = [
    path(
        "",
        ReviewRequestListView.as_view(),
        name="review-list",
    ),
    path(
        "<uuid:pk>/",
        ReviewRequestDetailView.as_view(),
        name="review-detail",
    ),
    path(
        "<uuid:pk>/edit/",
        ReviewProposalUpdateView.as_view(),
        name="review-edit",
    ),
    path(
        "<uuid:pk>/approve/",
        ApproveReviewRequestView.as_view(),
        name="review-approve",
    ),
    path(
        "<uuid:pk>/reject/",
        RejectReviewRequestView.as_view(),
        name="review-reject",
    ),
]