from django.urls import path

from . import views

app_name = "datasets"

urlpatterns = [
    path("vector/", views.VectorDatasetListView.as_view(), name="vector-list"),
    path(
        "vector/<int:pk>/",
        views.VectorDatasetDetailView.as_view(),
        name="vector-detail",
    ),
    path("scenario/", views.ScenarioListView.as_view(), name="scenario-list"),
    path(
        "scenario/<int:pk>/",
        views.ScenarioDetailView.as_view(),
        name="scenario-detail",
    ),
]
