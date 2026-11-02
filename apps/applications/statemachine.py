"""منبع حقیقت گردش وضعیت (data-model.md؛ FR-027)."""
from .models import Application

ALLOWED_TRANSITIONS = {
    Application.Status.NEW: {Application.Status.PHONE, Application.Status.INTERVIEW, Application.Status.REJECTED},
    Application.Status.PHONE: {Application.Status.INTERVIEW, Application.Status.REJECTED},
    Application.Status.INTERVIEW: {Application.Status.APPROVED, Application.Status.REJECTED},
    Application.Status.APPROVED: {Application.Status.HIRED, Application.Status.REJECTED},
}


def is_transition_allowed(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def is_final(status: str) -> bool:
    return status in Application.FINAL_STATUSES
