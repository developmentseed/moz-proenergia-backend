from django.conf import settings
from django.conf.urls import handler403
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter

from proenergia.datasets.views import error_403

router = DefaultRouter()
API_BASE_URL = "api/v1"

handler403 = error_403

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
    path(
        f"{API_BASE_URL}/tasks/",
        include(("proenergia.tasks.urls", "proenergia.tasks"), namespace="tasks"),
    ),
    path(f"{API_BASE_URL}/token-auth/", csrf_exempt(views.obtain_auth_token)),
]

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    *i18n_patterns(path("admin/", admin.site.urls)),
    path("", include(api_urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path(f"{API_BASE_URL}/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        f"{API_BASE_URL}/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # the 'api-root' from django rest-frameworks default router
    # http://www.django-rest-framework.org/api-guide/routers/#defaultrouter
    re_path(
        r"^$",
        RedirectView.as_view(url=settings.FRONTEND_URL, permanent=False),
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Debug Toolbar URLs (only in DEBUG mode)
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
