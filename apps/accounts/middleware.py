"""
انقضای بی‌فعالیتی نشست کارمند (FR-045؛ رفع یافته M3 در تحلیل — `STAFF_SESSION_IDLE_TIMEOUT_SECONDS`
در تنظیمات تعریف شده بود اما تا پیش از این هیچ‌جا اعمال نمی‌شد). سقف مطلق ۸ ساعته از قبل با
`SESSION_COOKIE_AGE` توسط خودِ Django اعمال می‌شود؛ این میانی‌افزار فقط بخش «۳۰ دقیقه بی‌فعالیتی»
را اضافه می‌کند. فقط روی نشست Django (کارمند) اثر دارد؛ نشست متقاضی کوکی امضاشده مستقل است
و اصلاً از این مسیر عبور نمی‌کند (اصل V).
"""
import time

from django.conf import settings


class StaffSessionIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = getattr(request, "session", None)
        if session is not None and session.session_key:
            now = time.time()
            last_activity = session.get("last_activity")
            if last_activity is not None and now - last_activity > settings.STAFF_SESSION_IDLE_TIMEOUT_SECONDS:
                session.flush()
            else:
                session["last_activity"] = now

        return self.get_response(request)
