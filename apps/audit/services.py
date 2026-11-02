"""سرویس مشترک ثبت حسابرسی که همه app ها از آن استفاده می‌کنند (FR-055)."""
from .models import AuditEvent


def record_event(
    *,
    action: str,
    staff_actor=None,
    candidate_actor=None,
    object_type: str = "",
    object_id: str = "",
    http_request_id: str = "",
    metadata: dict | None = None,
) -> AuditEvent:
    return AuditEvent.objects.create(
        action=action,
        staff_actor=staff_actor,
        candidate_actor=candidate_actor,
        object_type=object_type,
        object_id=str(object_id) if object_id else "",
        http_request_id=http_request_id,
        metadata=metadata or {},
    )
