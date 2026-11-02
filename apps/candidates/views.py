from django.middleware.csrf import get_token
from django.shortcuts import render

from apps.applications.models import PrivacyNotice
from apps.jobs.models import JobPosition


def home_page(request):
    """
    دروازهٔ ورودی پورتال (`/`). دو مسیر کاملاً مجزا را از همان لحظهٔ اول نشان می‌دهد: مراجعه‌کننده
    (ثبت درخواست/پیگیری، بدون ورود) و کارکنان (مدیریت، پشت فرم ورود). هیچ دادهٔ واقعی اینجا
    خوانده نمی‌شود — صرفاً یک صفحهٔ انتخاب مسیر است.
    """
    return render(request, "home.html")


def apply_page(request):
    """
    صفحه RTL ثبت درخواست همکاری (T035).
    `get_token` صراحتاً فراخوانی می‌شود تا کوکی csrftoken برای fetch بعدی جاوااسکریپت
    (static/js/csrf.js) صادر شود؛ بدون آن، هیچ مسیر `{% csrf_token %}` در این صفحه
    رندر نمی‌شد و تمام درخواست‌های POST بعدی با ۴۰۳ رد می‌شدند (باگ واقعی کشف‌شده در
    اجرای تست مرورگری Playwright).
    """
    get_token(request)
    jobs = JobPosition.objects.filter(status=JobPosition.Status.OPEN)
    notice = PrivacyNotice.objects.order_by("-published_at").first()
    return render(
        request,
        "candidate/apply.html",
        {"jobs": jobs, "privacy_notice_version": notice.version if notice else ""},
    )


def track_page(request):
    """صفحه RTL پیگیری درخواست با کد پیگیری — بدون OTP (اصل V نسخهٔ ۲.۰.۰)."""
    return render(request, "candidate/track.html")


def jobs_list_page(request):
    """
    صفحهٔ فهرست موقعیت‌های شغلی باز، بدون نیاز به ورود (FR-001, FR-002). خودِ فهرست همیشه از
    `GET /api/v1/jobs` (`PublicJobListView`, `AllowAny`) خوانده می‌شود، نه این صفحه؛ اینجا فقط
    قالب خالی رندر می‌شود تا تاریخچهٔ بدون داده‌ی سروری/دمو برای این مسیر هم رعایت شود.
    """
    return render(request, "candidate/jobs.html")
