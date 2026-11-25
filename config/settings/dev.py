"""本地开发配置：DEBUG、本机 MySQL/Redis。"""
from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "::1"]

SECRET_KEY = "dev-only-secret-key-not-for-production"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/0",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
