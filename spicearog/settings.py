"""
Django settings for the Spicearog project.

Faithful port of the Next.js + Prisma "spicearog" e-commerce platform.
"""
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-spicearog-dev-key-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # local apps
    "accounts",
    "store",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "spicearog.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_globals",
            ],
        },
    },
]

WSGI_APPLICATION = "spicearog.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# The original schema targets MySQL. We default to SQLite so the project runs
# out-of-the-box, and switch to MySQL automatically if DATABASE_URL is set to a
# mysql:// DSN (matching the original Prisma DATABASE_URL env var).
# ---------------------------------------------------------------------------
# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
        'options': '-c search_path=public',
        'connect_timeout': 10
        }
    }
}
# else:
#     DATABASES = {
#         "default": {
#             "ENGINE": "django.db.backends.sqlite3",
#             "NAME": BASE_DIR / "db.sqlite3",
#         }
#     }

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    # Sole backend: handles email/mobile login, INACTIVE blocking, and the
    # admin-login scope. ModelBackend is intentionally omitted — it ignores the
    # `scope` kwarg and would let non-admins through the admin login screen.
    # Permissions are resolved directly on the User model (has_perm etc.).
    "accounts.backends.EmailOrMobileBackend",
]

# bcrypt-first so passwords are interchangeable with the original Node/bcrypt app
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.BCryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
]

LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/account"
LOGOUT_REDIRECT_URL = "/"

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# ---- Storefront business constants (ported from src/lib/constants.ts) ----
SITE_NAME = "Spicearog"
HOME_PRODUCT_LIMIT = 20
HOME_BLOG_LIMIT = 5
HOME_TESTIMONIAL_LIMIT = 10
RELATED_PRODUCT_LIMIT = 10
FREE_DELIVERY_OVER = 499
SHIPPING_FEE = 49

# ---- Razorpay (optional) ----
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
