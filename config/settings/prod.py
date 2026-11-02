import os

from .base import *  # noqa: F401,F403

DEBUG = False

if not SECRET_KEY or SECRET_KEY == "insecure-dev-key-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY باید در تولید از محیط/مدیر راز تنظیم شود (FR-048).")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# پشت پراکسی معکوس TLS (Nginx/ALB): بدون این، Django خودِ درخواست را HTTP می‌بیند و
# SECURE_SSL_REDIRECT یک حلقهٔ ریدایرکت بی‌نهایت می‌سازد. مقدار از محیط خوانده می‌شود تا در
# محیط‌های بدون پراکسی روشن نشود.
_proxy_ssl_header = os.environ.get("SECURE_PROXY_SSL_HEADER")
if _proxy_ssl_header:
    _header_name, _header_value = (p.strip() for p in _proxy_ssl_header.split(",", 1))
    SECURE_PROXY_SSL_HEADER = (_header_name, _header_value)
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# هیچ مسیر دمو، دورزدن احراز هویت یا رمز مشترک مدیریتی در تولید وجود ندارد (FR-048, T069).
