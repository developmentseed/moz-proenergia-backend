from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path, reverse_lazy
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
API_BASE_URL = "api/v1"

api_urls = [
    path(
        f"{API_BASE_URL}/",
        include(("proenergia.users.urls", "proenergia.users"), namespace="users"),
    ),
    path(
        f"{API_BASE_URL}/",
        include(
            ("proenergia.datasets.urls", "proenergia.datasets"), namespace="datasets"
        ),
    ),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(api_urls)),
    path("api-token-auth/", views.obtain_auth_token),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path(f"{API_BASE_URL}/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        f"{API_BASE_URL}/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # the 'api-root' from django rest-frameworks default router
    # http://www.django-rest-framework.org/api-guide/routers/#defaultrouter
    re_path(r"^$", RedirectView.as_view(url=reverse_lazy("api-root"), permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
