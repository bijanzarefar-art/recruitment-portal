"""
تولید خروجی CSV/XLSX امن از پرونده‌های درخواست در دامنه مجوز کاربر (T055، FR-032 تا FR-037)،
و محدودیت نرخ اتمی خروجی (T057b، FR-037a).
"""
import csv
import io
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.cell.cell import WriteOnlyCell
from openpyxl.styles import numbers

from apps.applications.services import apply_staff_filters, get_applications_queryset

from .export_policy import (
    ALLOWED_COLUMNS,
    MAX_EXPORT_ROWS,
    TEXT_FORMAT_COLUMNS,
    TooManyRows,
    neutralize_formula,
    validate_columns,
)
from .models import ExportRateCounter

EXPORT_RATE_WINDOW_SECONDS = 600
EXPORT_RATE_LIMIT = 5


class ExportRateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__("حداکثر تعداد درخواست خروجی در این بازه رد شده است.")


def _window_start(now, bucket_seconds: int):
    epoch = int(now.timestamp())
    return timezone.datetime.fromtimestamp(epoch - (epoch % bucket_seconds), tz=dt_timezone.utc)


def enforce_export_rate_limit(staff_user) -> None:
    """
    افزایش اتمی شمارنده نرخ خروجی (دقیقاً همان الگوی `_increment_counter` در
    `apps.candidates.services`)؛ فقط پس از عبور از مجوز `IsHrManager` فراخوانی می‌شود.
    """
    now = timezone.now()
    window_start = _window_start(now, EXPORT_RATE_WINDOW_SECONDS)
    with transaction.atomic():
        counter, _ = ExportRateCounter.objects.select_for_update().get_or_create(
            staff_user_id=str(staff_user.id), window_start=window_start, defaults={"count": 0}
        )
        if counter.count >= EXPORT_RATE_LIMIT:
            window_end = window_start + timezone.timedelta(seconds=EXPORT_RATE_WINDOW_SECONDS)
            retry_after = max(1, int((window_end - now).total_seconds()))
            raise ExportRateLimitExceeded(retry_after)
        counter.count = counter.count + 1
        counter.save(update_fields=["count"])


def get_export_queryset(user, params):
    """
    همان پایه مجوز/فیلتر فهرست کارکنان (FR-036) — پارامترهای ارسالی هرگز نمی‌توانند دامنه
    `get_applications_queryset` را گسترش دهند، فقط می‌توانند آن را بیشتر محدود کنند.
    """
    base = get_applications_queryset(user).select_related("job_position")
    filtered = apply_staff_filters(base, params)
    return filtered.order_by("-created_at", "id")


def _row_values(application, columns):
    for column in columns:
        if column == "job_position_title":
            yield application.job_position.title
        else:
            yield getattr(application, column)


def collect_rows(queryset, columns):
    """
    حداکثر `MAX_EXPORT_ROWS + 1` ردیف را می‌خواند تا عبور از سقف بدون شمارش کامل جدول تشخیص
    داده شود (FR-032)؛ هرگز محتوای باینری رزومه را واکشی نمی‌کند (فقط فیلدهای `Application`/
    `JobPosition.title`، بدون هیچ `select_related`/فیلد از `AttachmentContent`).
    """
    limited = list(queryset[: MAX_EXPORT_ROWS + 1])
    if len(limited) > MAX_EXPORT_ROWS:
        raise TooManyRows()
    return [list(_row_values(app, columns)) for app in limited]


def render_csv(columns, rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([ALLOWED_COLUMNS[c] for c in columns])
    for row in rows:
        writer.writerow([neutralize_formula(value) for value in row])
    # BOM مناسب برای UTF-8 تا Excel فارسی را درست نمایش دهد (FR-034).
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def render_xlsx(columns, rows) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("applications")

    header_row = [WriteOnlyCell(sheet, value=ALLOWED_COLUMNS[c]) for c in columns]
    sheet.append(header_row)

    for row in rows:
        cells = []
        for column, value in zip(columns, row):
            cell = WriteOnlyCell(sheet, value=neutralize_formula(value))
            if column in TEXT_FORMAT_COLUMNS:
                cell.number_format = numbers.FORMAT_TEXT
            cells.append(cell)
        sheet.append(cells)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_export(*, user, params, columns, export_format: str):
    """
    خروجی نهایی (bytes، content_type، نام فایل) را برمی‌گرداند یا `TooManyRows` را raise می‌کند.
    """
    validated_columns = validate_columns(columns)
    queryset = get_export_queryset(user, params)
    rows = collect_rows(queryset, validated_columns)

    if export_format == "xlsx":
        content = render_xlsx(validated_columns, rows)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "applications_export.xlsx"
    else:
        content = render_csv(validated_columns, rows)
        content_type = "text/csv; charset=utf-8"
        filename = "applications_export.csv"

    return content, content_type, filename, validated_columns, len(rows)
