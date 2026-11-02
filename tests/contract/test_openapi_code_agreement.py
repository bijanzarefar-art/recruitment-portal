"""
T068 رگرسیون: قرارداد `contracts/openapi.yaml` باید با رفتار واقعی کد هم‌راستا بماند. این تست
مواردی را که در تطبیق ۲۳ مسیر واقعاً مغایرت داشتند و اصلاح شدند، قفل می‌کند تا دوباره بی‌صدا
واگرا نشوند — نه یک اعتبارسنجی عمومی کامل OpenAPI.
"""
import pytest
import yaml
from django.conf import settings
from rest_framework.test import APIClient

from apps.applications.models import Application
from apps.attachments.api.serializers import UploadStatusSerializer

pytestmark = pytest.mark.django_db

CONTRACT_PATH = settings.BASE_DIR / "specs" / "001-recruitment-portal" / "contracts" / "openapi.yaml"


def _load_contract():
    with open(CONTRACT_PATH) as f:
        return yaml.safe_load(f)


def test_every_path_has_explicit_security_declaration():
    doc = _load_contract()
    assert len(doc["paths"]) == 23
    for path, methods in doc["paths"].items():
        for method, body in methods.items():
            assert "security" in body, f"{method.upper()} {path} ندارد `security` صریح"


def test_protected_paths_all_use_the_correct_session_domain():
    """هیچ مسیر staff/* نباید به candidateSession اتکا کند و بالعکس."""
    doc = _load_contract()
    for path, methods in doc["paths"].items():
        for method, body in methods.items():
            security = body.get("security", [])
            if security == []:
                continue
            if path.startswith("/staff/"):
                assert security == [{"staffSession": []}], f"{method.upper()} {path}"
            elif path.startswith("/candidate/"):
                assert security == [{"candidateSession": []}], f"{method.upper()} {path}"


def test_upload_status_schema_matches_serializer_fields():
    contract = _load_contract()
    contract_fields = set(contract["components"]["schemas"]["UploadStatus"]["properties"].keys())
    serializer_fields = set(UploadStatusSerializer().fields.keys())
    assert contract_fields == serializer_fields


def test_staff_detail_previous_applications_and_status_history_keys_match_serializer(
    candidate_factory, job_position_factory, hr_manager
):
    from apps.applications.api.serializers import ApplicationStaffDetailSerializer
    from apps.applications.models import StatusHistory

    contract = _load_contract()
    detail_schema = contract["components"]["schemas"]["ApplicationStaffDetail"]["properties"]
    expected_prev_keys = set(detail_schema["previous_applications"]["items"]["properties"].keys())
    expected_hist_keys = set(detail_schema["status_history"]["items"]["properties"].keys())

    candidate = candidate_factory()
    job = job_position_factory()
    other_app = Application.objects.create(
        tracking_code="contractother1",
        candidate=candidate,
        job_position=job,
        first_name="a",
        last_name="b",
        mobile_snapshot=candidate.mobile,
        city="تهران",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        status=Application.Status.REJECTED,
        idempotency_key="contract-k0",
    )
    app = Application.objects.create(
        tracking_code="contracttst01",
        candidate=candidate,
        job_position=job,
        first_name="a",
        last_name="b",
        mobile_snapshot=candidate.mobile,
        city="تهران",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        status=Application.Status.NEW,
        idempotency_key="contract-k1",
    )
    StatusHistory.objects.create(application=app, from_status="new", to_status="new")

    serializer = ApplicationStaffDetailSerializer(
        app,
        context={
            "request": "dummy",  # get_previous_applications فقط None بودن را بررسی می‌کند.
            "allowed_queryset": Application.objects.filter(id__in=[app.id, other_app.id]),
        },
    )
    data = serializer.data
    assert set(data.keys()) == set(detail_schema.keys())
    assert len(data["previous_applications"]) == 1
    assert set(data["previous_applications"][0].keys()) == expected_prev_keys
    assert len(data["status_history"]) == 1
    assert set(data["status_history"][0].keys()) == expected_hist_keys


def test_staff_list_response_never_includes_detail_only_fields(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """قرارداد قبلاً فهرست را با `ApplicationStaffDetail` توصیف می‌کرد، درحالی‌که فهرست واقعاً سبک‌تر است."""
    from apps.applications.services import assign_reviewer

    candidate = candidate_factory()
    job = job_position_factory()
    app = Application.objects.create(
        tracking_code="contractlist01",
        candidate=candidate,
        job_position=job,
        first_name="a",
        last_name="b",
        mobile_snapshot=candidate.mobile,
        city="تهران",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        status=Application.Status.NEW,
        idempotency_key="contract-list-k1",
    )
    assign_reviewer(application=app, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.get("/api/v1/staff/applications")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert "results" in body
    result = body["results"][0]
    assert "notes" not in result
    assert "status_history" not in result
    assert "version" not in result


def test_jobs_public_list_only_returns_open_and_matches_schema(candidate_factory):
    doc = _load_contract()
    schema_keys = set(doc["components"]["schemas"]["JobPositionPublic"]["properties"].keys())
    client = APIClient()
    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    for item in resp.json():
        assert set(item.keys()) == schema_keys


def test_privacy_notice_is_public_and_matches_schema():
    """ردیف ۲ ماتریس: هیچ آزمونی برای این مسیر وجود نداشت."""
    from django.utils import timezone

    from apps.applications.models import PrivacyNotice

    PrivacyNotice.objects.create(version="matrix-v1", body="متن نمونه", published_at=timezone.now())
    client = APIClient()
    resp = client.get("/api/v1/privacy-notice")
    assert resp.status_code == 200
    body = resp.json()
    expected = set(_load_contract()["components"]["schemas"]["PrivacyNotice"]["properties"].keys())
    assert set(body.keys()) == expected
    assert body["version"] == "matrix-v1"


def test_non_hr_staff_with_valid_session_cannot_patch_job(job_position_factory, recruiter):
    """ردیف ۲۳ ماتریس: کارمند غیر-HR با نشست معتبر باید ۴۰۳ بگیرد، نه فقط کاربر ناشناس."""
    job = job_position_factory()
    client = APIClient()
    client.force_authenticate(user=recruiter)
    resp = client.patch(f"/api/v1/staff/jobs/{job.id}", {"title": "تغییر غیرمجاز"}, format="json")
    assert resp.status_code == 403
    job.refresh_from_db()
    assert job.title != "تغییر غیرمجاز"


def test_non_hr_staff_cannot_change_job_status_with_valid_session(job_position_factory, recruiter):
    """ردیف ۲۴ ماتریس."""
    job = job_position_factory()
    client = APIClient()
    client.force_authenticate(user=recruiter)
    resp = client.patch(f"/api/v1/staff/jobs/{job.id}/status", {"status": "closed"}, format="json")
    assert resp.status_code == 403


def test_non_hr_staff_cannot_list_jobs_with_valid_session(recruiter):
    """ردیف ۲۲ ماتریس: GET /staff/jobs فقط برای hr_manager است."""
    client = APIClient()
    client.force_authenticate(user=recruiter)
    assert client.get("/api/v1/staff/jobs").status_code == 403
