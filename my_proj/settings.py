"""
my_proj/settings.py

تغییرات اصلی نسبت به نسخه‌ی قبلی:
- هیچ رمز/کلیدی داخل کد نیست؛ همه از متغیرهای محیطی (.env) خوانده می‌شوند.
- مسیر GDAL/GEOS فقط روی ویندوز و فقط اگر واقعاً لازم باشد ست می‌شود.
- STATIC_ROOT اضافه شد تا collectstatic کار کند.
- به‌جای print() از logging استاندارد جنگو استفاده شده.
- تنظیمات امنیتی production پشت DEBUG=False فعال می‌شوند.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# محیط / کلیدهای حساس
# ---------------------------------------------------------------------------
# نصب کنید: pip install python-decouple  (یا django-environ)
# یک فایل .env در کنار manage.py بسازید و هرگز آن را commit نکنید.
try:
    from decouple import config, Csv
except ImportError:
    # fallback بسیار ساده اگر python-decouple نصب نبود، تا پروژه کرش نکند
    def config(key, default=None, cast=None):
        val = os.environ.get(key, default)
        if cast and val is not None:
            return cast(val)
        return val

    def Csv():
        return lambda v: [x.strip() for x in v.split(',') if x.strip()]

SECRET_KEY = config('DJANGO_SECRET_KEY')  # اجباری - بدون مقدار پیش‌فرض
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())

# ---------------------------------------------------------------------------
# GDAL / GEOS - فقط روی ویندوز لازم است؛ روی لینوکس/داکر این‌ها معمولاً
# در PATH سیستم هستند و نباید هاردکد شوند.
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    OSGEO4W_ROOT = config('OSGEO4W_ROOT', default=r'C:\OSGeo4W')
    os.environ['PATH'] = os.path.join(OSGEO4W_ROOT, 'bin') + os.pathsep + os.environ.get('PATH', '')
    GDAL_LIBRARY_PATH = config(
        'GDAL_LIBRARY_PATH',
        default=os.path.join(OSGEO4W_ROOT, 'bin', 'gdal313.dll')
    )
    GEOS_LIBRARY_PATH = config(
        'GEOS_LIBRARY_PATH',
        default=os.path.join(OSGEO4W_ROOT, 'bin', 'geos_c.dll')
    )
# روی لینوکس/مک چیزی ست نکنید؛ اگر لازم بود از متغیر محیطی GDAL_LIBRARY_PATH
# در .env استفاده کنید، بدون شرط پلتفرم.

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'smart_selects',
    'rest_framework',  # اضافه شد: surveys/views.py از rest_framework.viewsets
                       # استفاده می‌کند ولی این اپ اصلاً در لیست نبود؛ بدون آن
                       # هر ویویی که از آن import می‌کرد در عمل با خطا مواجه می‌شد.

    # اپلیکیشن‌های پروژه
    'accounts',
    'surveys',
    'farms',
    'irrigation',
    'indicators',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'my_proj.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'my_proj.wsgi.application'

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME', default='water_management'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD'),  # اجباری - بدون پیش‌فرض
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # هدف collectstatic - قبلاً تعریف نشده بود
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
]
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend' if DEBUG
    else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@yourfarm.ir')

USE_DJANGO_JQUERY = True

# ---------------------------------------------------------------------------
# Celery - قبلاً هیچ تنظیماتی نبود، در حالی که surveys/tasks.py به آن متکی بود
# (نگاه کنید به my_proj/celery.py برای جزئیات بیشتر)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# ---------------------------------------------------------------------------
# امنیت - فقط وقتی DEBUG خاموش است (یعنی در production)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# ---------------------------------------------------------------------------
# Logging - جایگزین print() های پراکنده در کل پروژه
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}
