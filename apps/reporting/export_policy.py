"""
سیاست ستون‌های مجاز خروجی و خنثی‌سازی فرمول (T055، FR-032 تا FR-035، research.md §۷).
یادداشت داخلی و داده حسابرسی عمداً در این فهرست حضور ندارند — نه فقط از پیش‌فرض حذف شده‌اند.
"""
from collections import OrderedDict

MAX_EXPORT_ROWS = 10_000

# کلید -> عنوان ستون در خروجی. ترتیب درج، ترتیب ستون‌های فایل را هم مشخص می‌کند.
ALLOWED_COLUMNS = OrderedDict(
    [
        ("tracking_code", "کد پیگیری"),
        ("first_name", "نام"),
        ("last_name", "نام خانوادگی"),
        ("mobile_snapshot", "موبایل"),
        ("email", "ایمیل"),
        ("city", "شهر"),
        ("job_position_title", "موقعیت شغلی"),
        ("employment", "وضعیت اشتغال"),
        ("experience", "سابقه کاری"),
        ("availability", "امکان شروع"),
        ("last_title", "آخرین عنوان شغلی"),
        ("last_company", "آخرین شرکت"),
        ("status", "وضعیت"),
        ("created_at", "تاریخ ثبت"),
        ("updated_at", "آخرین به‌روزرسانی"),
    ]
)

# ستون‌هایی که باید در XLSX با قالب سلول متنی صریح (`@`) نوشته شوند تا صفر ابتدایی حفظ شود
# (FR-034). شناسه‌های داخلی/شماره‌ای که صفر ابتدایی دارند هم باید اینجا اضافه شوند.
TEXT_FORMAT_COLUMNS = {"mobile_snapshot", "tracking_code"}

DEFAULT_COLUMNS = list(ALLOWED_COLUMNS.keys())

_FORMULA_PREFIXES = ("=", "+", "-", "@")


class InvalidColumns(Exception):
    def __init__(self, invalid_keys):
        self.invalid_keys = invalid_keys
        super().__init__(f"ستون‌های نامجاز: {invalid_keys}")


class TooManyRows(Exception):
    pass


def validate_columns(requested_columns):
    """ستون‌های درخواستی را علیه فهرست مجاز سروری اعتبارسنجی می‌کند (FR-033)."""
    if not requested_columns:
        return list(DEFAULT_COLUMNS)
    invalid = [c for c in requested_columns if c not in ALLOWED_COLUMNS]
    if invalid:
        raise InvalidColumns(invalid)
    return list(requested_columns)


def neutralize_formula(value) -> str:
    """
    مقدار را به رشته تبدیل و در صورت شروع با `=`, `+`, `-`, `@` — حتی پس از حذف فاصله/نویسه
    کنترلی ابتدایی — با یک آپاستروف خنثی می‌کند تا در Excel به‌عنوان فرمول اجرا نشود (FR-035).
    """
    text = "" if value is None else str(value)
    stripped = text.lstrip(" \t\r\n\x0b\x0c")
    if stripped.startswith(_FORMULA_PREFIXES):
        # آپاستروف را پیش از بخش حذف‌شده‌ی اصلی (نه پیش از نسخه strip‌شده) درج می‌کنیم تا
        # فاصله/نویسه کنترلی ابتدایی اصلی برای خوانایی حفظ شود، اما مقدار همچنان خنثی باشد.
        leading_len = len(text) - len(stripped)
        return text[:leading_len] + "'" + text[leading_len:]
    return text
