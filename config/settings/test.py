"""测试配置：真实 MySQL 测试库（复用生产栈），缓存用本地内存避免污染 Redis。"""
from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = ["testserver"]

SECRET_KEY = "test-only-secret-key"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# 测试用固定私有签名密钥。
PRIVATE_SIGNING_KEY = "test-signing-key"
