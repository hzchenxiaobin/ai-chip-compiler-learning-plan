"""Django 基础配置（config.settings.base）。

环境差异见 dev.py / test.py / prod.py。
安全边界（设计文档 §9.4、§10.3）：
- 个人页面一律 no-store；公开页面缓存键包含 active_release。
- 会话 Cookie：HttpOnly、SameSite=Lax；生产额外 Secure。
- Redis 只作非权威缓存；MySQL 是学习数据唯一权威源。
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = "insecure-dev-key-change-me"  # dev 覆盖；prod 从环境变量读取

DEBUG = False

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.content",
    "apps.accounts",
    "apps.learning",
    "apps.search",
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

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# 数据库：MySQL（utf8mb4 / 严格模式 / UTC）。连接参数由各环境覆盖。
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "learning",
        "USER": "learning",
        "PASSWORD": "learning",
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {"CHARSET": "utf8mb4"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# 会话与 CSRF（设计文档 §9.3：同源 Session＋CSRF）
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "learnsite_sessionid"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 天
# fetch 写操作需要 JS 读取 csrftoken（Django 官方默认；HttpOnly 对 CSRF 无实际增益
# 且会破坏 AJAX 双提交，见 Django 文档 CSRF_COOKIE_HTTPONLY 说明）。
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "apps.accounts.views.csrf_failure"

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "var" / "static"

# 公开资源（源码 ZIP、日课图片）：Nginx/静态服务直接读取。
PUBLIC_ASSET_ROOT = BASE_DIR / "var" / "public-assets"
PUBLIC_ASSET_URL = "/assets/public/"
# 私有文件（导出、导入快照）：仅通过授权短时签名 URL 下载。
PRIVATE_ASSET_ROOT = BASE_DIR / "var" / "private-assets"
PRIVATE_ASSET_URL = "/assets/private/"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "var" / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
FIXTURE_DIRS = [BASE_DIR / "tests" / "fixtures"]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# 签名下载 URL 的有效时长（秒）。
SIGNED_URL_TTL = 300

# 导入/导出限额（设计文档 §8.4）。
IMPORT_MAX_FILE_BYTES = 5 * 1024 * 1024
IMPORT_MAX_DAY_RECORDS = 500

# 复用现有静态站资产。
VP_STATIC_VERSION = 6
