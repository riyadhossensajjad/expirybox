"""
Django settings for the ExpiryBox project.

ExpiryBox lets people track the expiry dates of things they own, get reminded
before they expire, and sell items that are expiring soon on a marketplace.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 on its servers. Locally nothing changes: debug mode,
# SQLite and photos saved in the media/ folder, exactly as before.
ON_VERCEL = os.environ.get("VERCEL") == "1"

# For local development only. Set DJANGO_SECRET_KEY in production (Vercel → Settings → Environment Variables).
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-shelflife-dev-key-change-me-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if ON_VERCEL else "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
if ON_VERCEL:
    ALLOWED_HOSTS += [".vercel.app"]
    # Vercel serves the site over https and passes requests on to Django.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"] + [
    f"https://{h.lstrip('.')}" for h in ALLOWED_HOSTS if h and h not in ("localhost", "127.0.0.1") and not h.endswith("vercel.app")
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Project apps (one per package in the class diagram)
    "accounts.apps.AccountsConfig",          # App1_Accounts
    "items.apps.ItemsConfig",                # App2_Items
    "notifications.apps.NotificationsConfig",  # App3_Notifications
    "impact.apps.ImpactConfig",              # App4_Impact
    "marketplace.apps.MarketplaceConfig",    # App5_Marketplace
    "filestore.apps.FilestoreConfig",        # uploaded photos kept in the database (used on Vercel)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Fires due expiry reminders and expires old items/listings (at most once a minute).
    "notifications.middleware.ReminderSweepMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.unread_notifications",
                "config.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# On Vercel the database is Postgres (Neon), given to the site as DATABASE_URL
# (or POSTGRES_URL). Without it, the local SQLite file is used.
_DB_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        # Performance: WAL lets reads and writes happen at the same time and avoids a
        # slow disk flush on every save (very noticeable on Windows). IMMEDIATE
        # transactions + a timeout stop "database is locked" errors under load.
        "OPTIONS": {
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA temp_store=MEMORY;"
                "PRAGMA cache_size=-20000;"
            ),
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}

if _DB_URL:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(_DB_URL, conn_max_age=60, conn_health_checks=True)}

# Sessions are read on every page; keep them in memory too (still saved to the database).
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "items:dashboard"
LOGOUT_REDIRECT_URL = "home"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded profile pictures and item photos
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Vercel's servers don't keep files written to disk, so there uploaded photos are
# saved in the database instead (see the filestore app). Locally: the media/ folder.
STORAGES = {
    "default": {
        "BACKEND": "filestore.storage.DatabaseStorage" if (ON_VERCEL or _DB_URL)
        else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MAX_UPLOAD_MB = 5

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- ExpiryBox settings -----------------------------------------------------
SITE_NAME = "ExpiryBox"
CURRENCY_SYMBOL = "৳"
# Days before expiry when automatic reminders fire.
REMINDER_OFFSETS_DAYS = [7, 3, 1, 0]
# Items expiring within this many days count as "expiring soon".
EXPIRING_SOON_DAYS = 7

MESSAGE_TAGS = {40: "error"}
