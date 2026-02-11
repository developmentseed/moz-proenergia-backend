import os
import sys
import tempfile

from .common import Common

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Local(Common):
    DEBUG = True

    # Testing
    INSTALLED_APPS = Common.INSTALLED_APPS
    INSTALLED_APPS += ("debug_toolbar",)
    
    # Debug Toolbar Middleware
    MIDDLEWARE = Common.MIDDLEWARE
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

    # Mail
    EMAIL_HOST = "localhost"
    EMAIL_PORT = 1025
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

    TESTING = "test" in sys.argv
    if TESTING:
        MEDIA_ROOT = tempfile.mkdtemp()
        CELERY_TASK_ALWAYS_EAGER = True
        CELERY_TASK_STORE_EAGER_RESULT = True
        CELERY_TASK_EAGER_PROPAGATES = True

    GDAL_LIBRARY_PATH = "/opt/homebrew/opt/gdal/lib/libgdal.dylib"
    GEOS_LIBRARY_PATH = "/opt/homebrew/opt/geos/lib/libgeos_c.dylib"
