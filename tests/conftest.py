"""
فیکسچرهای پایه pytest روی PostgreSQL واقعی (T005a، رفع یافته H2 در تحلیل).
همه تسک‌های تست در فازهای ۲ تا ۹ به این فیکسچرها وابسته‌اند.
"""
import factory
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.candidates.models import Candidate
from apps.jobs.models import JobPosition


class StaffUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StaffUser
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"staff{n}")
    role = StaffUser.Role.RECRUITER
    is_active = True


class CandidateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Candidate

    mobile = factory.Sequence(lambda n: f"0912000{n:04d}")


class JobPositionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobPosition

    title = factory.Sequence(lambda n: f"موقعیت شغلی {n}")
    status = JobPosition.Status.OPEN


@pytest.fixture
def staff_user_factory():
    return StaffUserFactory


@pytest.fixture
def candidate_factory():
    return CandidateFactory


@pytest.fixture
def job_position_factory():
    return JobPositionFactory


@pytest.fixture
def recruiter(db):
    return StaffUserFactory(role=StaffUser.Role.RECRUITER)


@pytest.fixture
def hiring_manager(db):
    return StaffUserFactory(role=StaffUser.Role.HIRING_MANAGER)


@pytest.fixture
def hr_manager(db):
    return StaffUserFactory(role=StaffUser.Role.HR_MANAGER)


@pytest.fixture
def system_operator(db):
    return StaffUserFactory(role=StaffUser.Role.SYSTEM_OPERATOR)


@pytest.fixture
def api_client():
    """فیکسچر HTTP client احرازهویت‌شده با force_authenticate برای هر نقش."""
    return APIClient()
