"""منبع حقیقت گردش وضعیت JobPosition (FR-039a، تصمیم صریح کاربر — نه ابهام)."""
from .models import JobPosition

ALLOWED_TRANSITIONS = {
    JobPosition.Status.DRAFT: {JobPosition.Status.OPEN},
    JobPosition.Status.OPEN: {JobPosition.Status.CLOSED},
    JobPosition.Status.CLOSED: {JobPosition.Status.OPEN},
}


def is_transition_allowed(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())
