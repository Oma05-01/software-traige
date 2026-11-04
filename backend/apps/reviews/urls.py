from django.urls import path

from apps.reviews.views import (
    ApproveReviewRequestView,
    RejectReviewRequestView,
    ReviewProposalUpdateView,
    ReviewRequestDetailView,
    ReviewRequestListView,
    RequestReviewChangesView,
    ReviseReviewRequestView,
    ClassificationReviewListView,
    ClassificationReviewDetailView,
    ClassificationReviewResolveView,
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
    path(
    "<uuid:pk>/request-changes/",
    RequestReviewChangesView.as_view(),
    name="review-request-changes",
    ),
    path(
        "<uuid:pk>/revise/",
        ReviseReviewRequestView.as_view(),
        name="review-revise",
    ),
    path(
        "classifications/",
        ClassificationReviewListView.as_view(),
        name="classification-list",
    ),
    path(
        "classifications/<uuid:pk>/",
        ClassificationReviewDetailView.as_view(),
        name="classification-detail",
    ),
    path(
        "classifications/<uuid:pk>/resolve/",
        ClassificationReviewResolveView.as_view(),
        name="classification-resolve",
    ),
]