"""
محدودسازی نرخ تلاش ورود کارمند (FR-047). بر اساس ترکیب **حساب** و **IP** — دو شمارندهٔ
مستقل با کنترل اتمیک در PostgreSQL (نه حافظهٔ یک process) تا میان چند worker سازگار باشد.

آستانه: FR-047 عدد دقیقی تعیین نکرده است. مقادیر پیش‌فرض زیر (۵/۱۵ دقیقه برای هر حساب،
۲۰/۱۵ دقیقه برای هر IP) در `settings` قابل‌تغییرند و به‌عنوان **پیشنهاد** تعریف شده‌اند، نه
سیاست مصوب؛ تصمیم نهایی مالک پروژه است (ثبت‌شده در `docs/decisions.md`).
"""
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.audit.services import record_event

from .models import StaffLoginRateCounter, StaffUser

# پنجره‌ها per-scope و از settings خوانده می‌شوند (D6): حساب ۱۵ دقیقه، IP ۲۰ دقیقه.


class StaffLoginRateLimitExceeded(Exception):
    def __init__(self, scope: str, retry_after_seconds: int):
        self.scope = scope
        self.retry_after_seconds = retry_after_seconds
        super().__init__(scope)


def _window_start(now, bucket_seconds: int):
    epoch = int(now.timestamp())
    return timezone.datetime.fromtimestamp(epoch - (epoch % bucket_seconds), tz=dt_timezone.utc)


def _client_ip(request) -> str:
    """
    آدرس کلاینت برای کلید rate limit (FR-047).

    هدر `X-Forwarded-For` **از سمت کلاینت قابل‌جعل است** و پیش‌فرض مورد اعتماد نیست: هر کلاینت
    می‌تواند با فرستادن یک مقدار تصادفی برای هر درخواست، کلید محدودیت را عوض کند و از سقف
    IP فرار کند. پس:
    - اگر `settings.TRUSTED_PROXY_COUNT == 0` (پیش‌فرض)، هدر کاملاً نادیده گرفته می‌شود و فقط
      `REMOTE_ADDR` (که خود پراکسی معکوس تنظیم می‌کند) ملاک است.
    - اگر برنامه پشت N پراکسی معتبر است، فقط N هاپ آخر زنجیره قابل‌اعتمادند؛ آدرس کلاینت واقعی
      عنصر `-(N+1)` از انتهای فهرست است. عناصر سمت چپ توسط کلاینت ساخته می‌شوند و کنار گذاشته
      می‌شوند — نه اینکه به‌عنوان آدرس معتبر پذیرفته شوند.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    trusted_hops = int(getattr(settings, "TRUSTED_PROXY_COUNT", 0) or 0)
    if trusted_hops <= 0:
        return remote_addr

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if not forwarded:
        return remote_addr

    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    if not chain:
        return remote_addr
    # N پراکسی معتبر هر کدام یک ورودی به انتهای زنجیره اضافه می‌کنند. برای N=1 (یک پراکسی)،
    # آخرین عنصر همان آدرس کلاینت واقعی است که پراکسی اضافه کرده؛ N-۱ عنصر آخر مال پراکسی‌های
    # داخلی‌تر است. عناصر سمت چپ را کلاینت ساخته و نباید باور شوند.
    #   N=1 → chain[-1]   N=2 → chain[-2]   ...   N=0 → هدر کامل نادیده
    index = len(chain) - trusted_hops
    if index < 0:
        return remote_addr
    return chain[index]


def _bump(scope: str, key: str, window_seconds: int, limit: int, now) -> None:
    """افزایش اتمی شمارندهٔ یک scope با پنجرهٔ زمانی مخصوص خودش."""
    window_start = _window_start(now, window_seconds)
    with transaction.atomic():
        counter, _ = StaffLoginRateCounter.objects.select_for_update().get_or_create(
            scope=scope, key=key, window_start=window_start, defaults={"count": 0}
        )
        if counter.count >= limit:
            window_end = window_start + timezone.timedelta(seconds=window_seconds)
            retry_after = max(1, int((window_end - now).total_seconds()))
            raise StaffLoginRateLimitExceeded(scope, retry_after)
        counter.count = counter.count + 1
        counter.save(update_fields=["count"])


def enforce_staff_login_rate_limit(*, username: str, request) -> None:
    """
    پیش از هر تلاش احراز هویت فراخوانی می‌شود (پس از قفل‌شدن خودِ حساب هم اجرا می‌شود،
    چون حتی تلاش‌های ردشده باید در کسر سهمیه اثر داشته باشند تا حملهٔ brute-force کند نشود).
    فراخوان در هر دو مسیر رمز و MFA است تا دورزدن از مسیر جایگزین ممکن نباشد.

    اگر `username` نامشخص باشد (مثلاً چالش MFA نامعتبر که پیش از حل‌شدن کاربر رد می‌شود)،
    فقط شمارندهٔ IP اعمال می‌شود — نه اینکه کل محدودیت دور زده شود.
    """
    now = timezone.now()
    account_key = (username or "").strip().lower()
    ip_key = _client_ip(request)

    if not account_key:
        _bump(
            StaffLoginRateCounter.Scope.IP,
            ip_key,
            settings.STAFF_LOGIN_IP_WINDOW_SECONDS,
            settings.STAFF_LOGIN_IP_LIMIT,
            now,
        )
        return

    _bump(
        StaffLoginRateCounter.Scope.ACCOUNT,
        account_key,
        settings.STAFF_LOGIN_ACCOUNT_WINDOW_SECONDS,
        settings.STAFF_LOGIN_ACCOUNT_LIMIT,
        now,
    )
    _bump(
        StaffLoginRateCounter.Scope.IP,
        ip_key,
        settings.STAFF_LOGIN_IP_WINDOW_SECONDS,
        settings.STAFF_LOGIN_IP_LIMIT,
        now,
    )


# --- مدیریت کاربران از پنل ادمین (US7، FR-021a تا FR-021d) ---
# «ادمین» = نقش موجود hr_manager (D10 در docs/decisions.md)، نه نقش جدید.


class DuplicateUsername(Exception):
    pass


class CannotDeactivateSelf(Exception):
    pass


class CannotDeleteSelf(Exception):
    pass


class LastActiveHrManager(Exception):
    pass


class UserHasProtectedRecords(Exception):
    """حذف ممکن نیست چون سوابق دیگری (بررسی/تخصیص درخواست، یادداشت و…) به این حساب وابسته‌اند."""

    pass


@transaction.atomic
def create_staff_account(*, created_by: StaffUser, username: str, password: str, role: str) -> StaffUser:
    """
    ساخت حساب تازه، بلافاصله با همان نام‌کاربری/رمز عبور قابل ورود (FR-021d؛ اصل V نسخهٔ ۳.۰.۰
    — بدون هیچ چرخهٔ راه‌اندازی عامل دوم).
    """
    if StaffUser.objects.filter(username=username).exists():
        raise DuplicateUsername()
    try:
        user = StaffUser.objects.create_user(
            username=username, password=password, role=role, created_by=created_by
        )
    except IntegrityError as exc:
        raise DuplicateUsername() from exc

    record_event(
        action="staff_account_created",
        staff_actor=created_by,
        object_type="StaffUser",
        object_id=str(user.id),
        metadata={"role": user.role},
    )
    return user


class OldPasswordIncorrect(Exception):
    pass


class PasswordNotAllowed(Exception):
    """رمز تازه از اعتبارسنجی‌های Django رد شده است (کوتاه، رایج، شبیه نام کاربری…)."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))


def _validate_new_password(user: StaffUser, new_password: str) -> None:
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise PasswordNotAllowed(list(exc.messages)) from exc


@transaction.atomic
def change_own_password(*, user: StaffUser, old_password: str, new_password: str) -> StaffUser:
    """
    تغییر رمز توسط خودِ کارمند (صفحهٔ «حساب من»). رمز فعلی الزامی است تا نشستِ بازشده روی
    دستگاهی که در اختیار کاربر نیست نتواند رمز را عوض کند و صاحب حساب را بیرون بیندازد.

    نکتهٔ Django: `set_password()` شناسهٔ نشست (`session_auth_hash`) را عوض می‌کند تا نشست‌های
    دیگر روی دستگاه‌های دیگر باطل شوند. برای همین، نشستِ فعلی (همین کاربری که الان رمز را
    عوض کرد) با `update_session_auth_hash` در ویو تازه می‌شود؛ وگرنه کاربر بلافاصله بیرون
    انداخته می‌شود — که یک نقص تجربهٔ کاربری واقعی بود (کشف‌شده در تست مرورگری).
    """
    if not user.check_password(old_password):
        raise OldPasswordIncorrect()

    _validate_new_password(user, new_password)

    user.set_password(new_password)
    user.save(update_fields=["password"])
    record_event(
        action="staff_password_changed",
        staff_actor=user,
        object_type="StaffUser",
        object_id=str(user.id),
        metadata={"by": "self"},
    )
    return user


@transaction.atomic
def admin_reset_password(*, changed_by: StaffUser, target_id, new_password: str) -> StaffUser:
    """
    بازنشانی رمز یک کارمند توسط مدیر HR — بدون دانستن رمز قبلی (برای حساب‌هایی که رمزشان
    فراموش شده). نقش و وضعیت فعال‌بودن تغییر نمی‌کند؛ فقط رمز.
    """
    if changed_by.role != StaffUser.Role.HR_MANAGER:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("فقط مدیر HR می‌تواند رمز دیگران را بازنشانی کند.")

    target = StaffUser.objects.select_for_update().get(id=target_id)
    _validate_new_password(target, new_password)

    target.set_password(new_password)
    target.save(update_fields=["password"])
    record_event(
        action="staff_password_reset",
        staff_actor=changed_by,
        object_type="StaffUser",
        object_id=str(target.id),
        metadata={"by": "hr_manager"},
    )
    return target


def _other_active_hr_manager_exists(target: StaffUser) -> bool:
    return (
        StaffUser.objects.select_for_update()
        .filter(role=StaffUser.Role.HR_MANAGER, is_active=True)
        .exclude(id=target.id)
        .exists()
    )


@transaction.atomic
def change_staff_role(*, changed_by: StaffUser, target_id, new_role: str) -> StaffUser:
    """
    اگر هدف تنها `hr_manager` فعال باشد، تغییر نقش او به نقشی غیر از `hr_manager` رد می‌شود —
    دقیقاً همان اثر غیرفعال‌سازی است (از دست رفتن آخرین مدیر HR فعال) و باید همان‌طور مسدود شود
    (رفع یک حفرهٔ واقعی کشف‌شده در آزمون دستی: بدون این بررسی، تنها `hr_manager` می‌توانست با
    تغییر نقش خودش کل سامانه را بدون هیچ مدیر HR فعال قفل کند).
    """
    target = StaffUser.objects.select_for_update().get(id=target_id)

    if target.role == StaffUser.Role.HR_MANAGER and new_role != StaffUser.Role.HR_MANAGER:
        if not _other_active_hr_manager_exists(target):
            raise LastActiveHrManager()

    old_role = target.role
    target.role = new_role
    target.save(update_fields=["role"])
    record_event(
        action="staff_role_changed",
        staff_actor=changed_by,
        object_type="StaffUser",
        object_id=str(target.id),
        metadata={"old_role": old_role, "new_role": new_role},
    )
    return target


@transaction.atomic
def set_staff_active(*, changed_by: StaffUser, target_id, is_active: bool) -> StaffUser:
    """
    غیرفعال‌سازی یعنی لغو فوری نشست فعال در درخواست بعدی (از طریق بررسی `is_active` موجود در
    `IsStaff`/بازسازی نشست Django — FR-021c). آخرین `hr_manager` فعال و حساب خودِ اجراکننده
    هرگز قابل‌غیرفعال‌سازی نیستند تا سامانه بدون هیچ مدیر HR فعال باقی نماند.
    """
    target = StaffUser.objects.select_for_update().get(id=target_id)

    if not is_active:
        if target.id == changed_by.id:
            raise CannotDeactivateSelf()
        if target.role == StaffUser.Role.HR_MANAGER and not _other_active_hr_manager_exists(target):
            raise LastActiveHrManager()

    target.is_active = is_active
    target.save(update_fields=["is_active"])
    record_event(
        action="staff_activated" if is_active else "staff_deactivated",
        staff_actor=changed_by,
        object_type="StaffUser",
        object_id=str(target.id),
    )
    return target


@transaction.atomic
def delete_staff_account(*, changed_by: StaffUser, target_id) -> None:
    """
    حذف دائمی یک حساب کارمند (نه فقط غیرفعال‌سازی). همان دو قفل ایمنی حذفِ عملیِ آخرین مدیر
    HR فعال و حذفِ حساب خودِ اجراکننده را دارد (مشابه `set_staff_active`)، به‌علاوهٔ یک قفل
    سوم: اگر سوابق دیگری (بررسی/تخصیص درخواست، یادداشت، پیام…) با `on_delete=PROTECT` به این
    حساب وابسته باشند، دیتابیس خودش حذف را رد می‌کند؛ آن خطا اینجا به `UserHasProtectedRecords`
    ترجمه می‌شود تا کاربر پیشنهاد غیرفعال‌سازی را به‌جای حذف ببیند (سابقهٔ حسابرسی دست‌نخورده
    می‌ماند چون `AuditEvent.staff_actor` خودش `SET_NULL` است، نه `PROTECT`).
    """
    target = StaffUser.objects.select_for_update().get(id=target_id)

    if target.id == changed_by.id:
        raise CannotDeleteSelf()
    if target.role == StaffUser.Role.HR_MANAGER and not _other_active_hr_manager_exists(target):
        raise LastActiveHrManager()

    username = target.username
    try:
        target.delete()
    except ProtectedError as exc:
        raise UserHasProtectedRecords() from exc

    record_event(
        action="staff_account_deleted",
        staff_actor=changed_by,
        object_type="StaffUser",
        object_id=str(target_id),
        metadata={"username": username},
    )
