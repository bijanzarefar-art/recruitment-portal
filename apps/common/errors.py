"""
ساختار خطای مشترک API: {code, message, field_errors, request_id} (plan.md «قرارداد اولیه API»).
جزئیات خطای داخلی هرگز افشا نمی‌شود.
"""
import uuid

from rest_framework.views import exception_handler


def envelope_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    request = context.get("request")
    request_id = getattr(request, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())

    detail = response.data
    field_errors = detail if isinstance(detail, dict) else None
    message = detail.get("detail") if isinstance(detail, dict) and "detail" in detail else "خطا در پردازش درخواست"

    response.data = {
        "code": _code_for_status(response.status_code),
        "message": str(message),
        "field_errors": field_errors if field_errors and "detail" not in field_errors else None,
        "request_id": request_id,
    }
    return response


def _code_for_status(status_code: int) -> str:
    return {
        400: "validation_error",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        415: "unsupported_media_type",
        429: "rate_limited",
    }.get(status_code, "error")
