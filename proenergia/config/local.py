import os
import sys
import tempfile

from .common import Common

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Local(Common):
    DEBUG = True

    # Testing
    TESTING = "test" in sys.argv

    INSTALLED_APPS = Common.INSTALLED_APPS
    MIDDLEWARE = Common.MIDDLEWARE

    if not TESTING:
        INSTALLED_APPS += ("debug_toolbar",)

        # Debug Toolbar Middleware
        MIDDLEWARE = list(MIDDLEWARE)
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

        # Debug Toolbar Configuration
        INTERNAL_IPS = [
            "127.0.0.1",
            "localhost",
        ]

        DEBUG_TOOLBAR_CONFIG = {
            "SHOW_TOOLBAR_CALLBACK": lambda request: True,
            "SHOW_COLLAPSED": True,
        }

    # Mail - Read from environment with fallbacks for local development
    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
    )
    EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "1025"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() in ["true", "1", "yes"]
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ["true", "1", "yes"]
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "webmaster@localhost")
    SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
    
    # URLs - Read from environment with fallbacks
    BACKEND_URL = os.getenv("BACKEND_URL", Common.BACKEND_URL)
    FRONTEND_URL = os.getenv("FRONTEND_URL", Common.FRONTEND_URL)

    if TESTING:
        MEDIA_ROOT = tempfile.mkdtemp()
        CELERY_TASK_ALWAYS_EAGER = True
        CELERY_TASK_STORE_EAGER_RESULT = True
        CELERY_TASK_EAGER_PROPAGATES = True


    GDAL_LIBRARY_PATH = "/opt/homebrew/opt/gdal/lib/libgdal.dylib"
    GEOS_LIBRARY_PATH = "/opt/homebrew/opt/geos/lib/libgeos_c.dylib"
