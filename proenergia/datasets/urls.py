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
    path("model/", views.DataModelListView.as_view(), name="model-list"),
    path(
        "model/<int:pk>/",
        views.DataModelDetailView.as_view(),
        name="model-detail",
    ),
    path(
        "scenario/<int:scenario_id>/feature/<int:pk>/",
        views.ScenarioDataDetailView.as_view(),
        name="feature-detail",
    ),
    path(
        "scenario/<int:pk>/summaries/",
        views.MultiFieldSummaryView.as_view(),
        name="scenario-summaries",
    ),
    path(
        "scenario/<int:pk>/summaries/cache/",
        views.PurgeSummaryCacheView.as_view(),
        name="scenario-summaries-cache",
    ),
]
