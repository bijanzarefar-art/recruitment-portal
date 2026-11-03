from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.shortcuts import render

STAFF_LOGIN_URL = "/staff/login"


def staff_login_page(request):
    """صفحه RTL ورود کارمند؛ فقط نام‌کاربری/رمز عبور، بدون عامل دوم (اصل V نسخهٔ ۳.۰.۰)."""
    get_token(request)
    return render(request, "staff/login.html")


@login_required(login_url=STAFF_LOGIN_URL)
def staff_dashboard_page(request):
    """
    داشبورد HR (T045). خودِ صفحه حالا پشت نشست کارمند قفل است (کاربر ناشناس به /staff/login
    هدایت می‌شود)؛ این جدا از کنترل مجوز واقعی API است — داده همچنان فقط از طریق fetch به API
    خوانده می‌شود، نه سروری/دمو.
    """
    get_token(request)
    return render(request, "staff/dashboard.html")


@login_required(login_url=STAFF_LOGIN_URL)
def staff_application_detail_page(request, pk):
    """صفحه جزئیات پرونده (T045)؛ خودِ داده از API (با کنترل مجوز رکورد سروری) خوانده می‌شود."""
    get_token(request)
    return render(request, "staff/application_detail.html", {"application_id": pk})


@login_required(login_url=STAFF_LOGIN_URL)
def staff_export_page(request):
    """صفحه انتخاب خروجی (T057)؛ مجوز واقعی فقط در `POST /api/v1/staff/exports` بررسی می‌شود."""
    get_token(request)
    return render(request, "staff/export.html")


@login_required(login_url=STAFF_LOGIN_URL)
def staff_jobs_page(request):
    """صفحه مدیریت موقعیت‌های شغلی (T061)؛ مجوز واقعی در `apps/jobs/api/views.py` بررسی می‌شود."""
    get_token(request)
    return render(request, "staff/jobs.html")


@login_required(login_url=STAFF_LOGIN_URL)
def staff_account_page(request):
    """صفحهٔ «حساب من»: هر کارمند رمز خودش را عوض می‌کند (رمز فعلی الزامی است)."""
    get_token(request)
    return render(request, "staff/account.html")


@login_required(login_url=STAFF_LOGIN_URL)
def staff_pipeline_page(request):
    """
    صفحه گردش جذب (Kanban): پرونده‌ها بر اساس وضعیت دسته‌بندی می‌شوند و قواعد گذار/نقش کنار
    هر ستون نمایش داده می‌شود. فهرست واقعی از همان `GET /api/v1/staff/applications` خوانده
    می‌شود (همان دامنهٔ مجوز `get_applications_queryset` که داشبورد هم استفاده می‌کند)؛ اینجا
    فقط چیدمان نمایش فرق دارد، نه منبع داده یا کنترل دسترسی.
    """
    get_token(request)
    return render(request, "staff/pipeline.html")


@login_required(login_url=STAFF_LOGIN_URL)
def staff_users_page(request):
    """
    صفحه مدیریت کاربران از پنل ادمین (US7). رندر صفحه فقط نیازمند نشست کارمند معتبر است، نه
    نقش hr_manager — هر دادهٔ واقعی از `/api/v1/staff/users` خوانده می‌شود که با `IsHrManager`
    محافظت می‌شود (اصل III). قفل سطح صفحه فقط مانع دسترسی کاربر کاملاً ناشناس می‌شود.
    """
    get_token(request)
    return render(request, "staff/users.html")
