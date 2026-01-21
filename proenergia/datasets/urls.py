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
]
