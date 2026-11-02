from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsHrManager
from apps.audit.services import record_event

from ..export_policy import ALLOWED_COLUMNS, InvalidColumns, TooManyRows
from ..services import ExportRateLimitExceeded, build_export, enforce_export_rate_limit


def _normalized_filters(params: dict) -> dict:
    allowed_filter_keys = (
        "status",
        "job_position",
        "city",
        "experience",
        "date_from",
        "date_to",
        "reviewer",
        "q",
    )
    return {key: params[key] for key in allowed_filter_keys if params.get(key)}


class StaffExportView(APIView):
    """
    POST /api/v1/staff/exports (T056، FR-032 تا FR-037). فقط `hr_manager` — مجوز خروجی مستقل از
    مجوز مشاهده بررسی می‌شود (FR-036)؛ همان پایه/فیلترهای فهرست کارکنان اعمال می‌شود تا
    پارامترهای ارسالی هرگز نتوانند دامنه مجاز را گسترش دهند. شروع و نتیجه (بدون محتوای واقعی
    خروجی) حسابرسی می‌شود (FR-037).
    """

    permission_classes = [IsHrManager]

    def post(self, request):
        # محدودیت نرخ بلافاصله پس از عبور از IsHrManager (احراز هویت کامل + مجوز خروجی) و پیش
        # از هر اعتبارسنجی/ساخت فایل دیگری اعمال می‌شود (FR-037a).
        try:
            enforce_export_rate_limit(request.user)
        except ExportRateLimitExceeded as exc:
            response = Response(
                {
                    "code": "rate_limited",
                    "message": "تعداد درخواست خروجی در این بازه از سقف مجاز عبور کرده؛ کمی بعد دوباره تلاش کنید.",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(exc.retry_after_seconds)
            return response

        body = request.data if isinstance(request.data, dict) else {}
        export_format = body.get("format", "csv")
        if export_format not in ("csv", "xlsx"):
            return Response(
                {
                    "code": "validation_error",
                    "message": "فرمت خروجی باید csv یا xlsx باشد.",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        columns = body.get("columns") or None
        filters = _normalized_filters(body)

        record_event(
            action="export_started",
            staff_actor=request.user,
            object_type="Application",
            metadata={"format": export_format, "filters": filters, "columns": columns or list(ALLOWED_COLUMNS)},
        )

        try:
            content, content_type, filename, used_columns, row_count = build_export(
                user=request.user, params=filters, columns=columns, export_format=export_format
            )
        except InvalidColumns as exc:
            record_event(
                action="export_failed",
                staff_actor=request.user,
                object_type="Application",
                metadata={"reason": "invalid_columns", "invalid_keys": exc.invalid_keys},
            )
            return Response(
                {
                    "code": "validation_error",
                    "message": f"ستون‌های نامجاز: {', '.join(exc.invalid_keys)}",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TooManyRows:
            record_event(
                action="export_failed",
                staff_actor=request.user,
                object_type="Application",
                metadata={"reason": "row_limit_exceeded", "filters": filters},
            )
            return Response(
                {
                    "code": "validation_error",
                    "message": "تعداد ردیف‌های منطبق با فیلتر بیش از ۱۰٬۰۰۰ است؛ فیلترها را محدودتر کنید.",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        record_event(
            action="export_completed",
            staff_actor=request.user,
            object_type="Application",
            metadata={"format": export_format, "filters": filters, "columns": used_columns, "row_count": row_count},
        )

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
