"""
فیلتر قالب مشترک تبدیل میلادی→شمسی برای لایه ارائه (T021a، FR-058).
ذخیره همیشه UTC است؛ این فیلتر فقط در HTML/خروجی قابل‌مشاهده انسانی به کار می‌رود.
"""
import jdatetime
from django import template
from django.utils import timezone

register = template.Library()

TEHRAN_TZ = timezone.get_fixed_timezone(210)  # Asia/Tehran = UTC+3:30


@register.filter(name="to_jalali")
def to_jalali(value, fmt: str = "%Y/%m/%d %H:%M"):
    """تبدیل datetime (UTC، aware) به تاریخ/ساعت شمسی منطقه Asia/Tehran."""
    if value is None:
        return ""
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.utc)
    local_dt = value.astimezone(TEHRAN_TZ)
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=local_dt)
    return jalali_dt.strftime(fmt)
