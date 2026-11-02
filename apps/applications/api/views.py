from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import StaffUser
from apps.accounts.permissions import IsStaff, IsHrManager
from apps.attachments.models import AttachmentContent
from apps.audit.services import record_event
from apps.candidates.services import TrackingRateLimitExceeded, enforce_tracking_rate_limit
from apps.jobs.models import JobPosition

from ..models import Application, PrivacyNotice
from ..services import (
    AssignmentConflict,
    AttachmentNotReady,
    DuplicateActiveApplication,
    IdempotencyConflict,
    InvalidTransition,
    JobNotOpen,
    ReasonRequired,
    VersionConflict,
    add_note,
    apply_staff_filters,
    assign_reviewer,
    change_status,
    get_applications_queryset,
    lookup_by_tracking_code,
    revoke_reviewer,
    submit_application,
)
from .serializers import (
    ApplicationCreateSerializer,
    ApplicationPublicDetailSerializer,
    ApplicationReceiptSerializer,
    ApplicationStaffDetailSerializer,
    ApplicationStaffListSerializer,
    AssignmentSerializer,
    NoteCreateSerializer,
    NoteSerializer,
    PrivacyNoticeSerializer,
    StatusChangeSerializer,
)


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


class CurrentPrivacyNoticeView(RetrieveAPIView):
    """GET /api/v1/privacy-notice — متن و نسخه جاری (FR-004)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PrivacyNoticeSerializer

    def get_object(self):
        return PrivacyNotice.objects.order_by("-published_at").first()


class CandidateApplicationCreateView(APIView):
    """
    POST /api/v1/candidate/applications — ثبت درخواست بدون هیچ احراز هویتی (اصل V نسخهٔ
    ۲.۰.۰؛ FR-003, FR-007 تا FR-009). `mobile` مستقیماً از بدنهٔ فرم خوانده می‌شود؛ پیگیری
    بعدی فقط با کد پیگیری انجام می‌شود (`GET /api/v1/track/{tracking_code}`، نه این مسیر).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"code": "validation_error", "message": "هدر Idempotency-Key اجباری است.", "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload_attempt_key = request.headers.get("X-Upload-Attempt-Key", "")
        if not upload_attempt_key:
            return Response(
                {
                    "code": "validation_error",
                    "message": "هدر X-Upload-Attempt-Key اجباری است.",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)
        mobile = validated.pop("mobile")

        job_position = get_object_or_404(JobPosition, id=validated["job_position"])
        validated["job_position_obj"] = job_position

        try:
            application = submit_application(
                mobile=mobile,
                upload_attempt_key=upload_attempt_key,
                idempotency_key=idempotency_key,
                data=validated,
            )
        except JobNotOpen:
            return Response(
                {"code": "validation_error", "message": "این موقعیت دیگر باز نیست.", "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except AttachmentNotReady:
            return Response(
                {"code": "validation_error", "message": "فایل رزومه سالم و آماده نیست.", "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DuplicateActiveApplication:
            return Response(
                {"code": "conflict", "message": "شما درخواست فعالی برای این موقعیت دارید.", "field_errors": None, "request_id": ""},
                status=status.HTTP_409_CONFLICT,
            )
        except IdempotencyConflict:
            return Response(
                {"code": "conflict", "message": "کلید تکرارپذیری تکراری با بدنه متفاوت.", "field_errors": None, "request_id": ""},
                status=status.HTTP_409_CONFLICT,
            )

        receipt = ApplicationReceiptSerializer(application).data
        http_status = status.HTTP_201_CREATED if application.status else status.HTTP_200_OK
        return Response(receipt, status=http_status)


class TrackApplicationView(APIView):
    """
    GET /api/v1/track/{tracking_code} — پیگیری عمومی بدون هیچ احراز هویتی (اصل V نسخهٔ
    ۲.۰.۰؛ FR-012, FR-015, FR-016). نرخ‌محدودسازی بر اساس IP پیش از هر جست‌وجوی دیتابیس
    اعمال می‌شود (FR-043)؛ برای کد نامعتبر/ناموجود پاسخ کاملاً یکسان ۴۰۴ برمی‌گردد (FR-044) —
    هرگز یادداشت/ارجاع/دلیل داخلی/هویت کارمند در پاسخ نیست (FR-015).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, tracking_code):
        try:
            enforce_tracking_rate_limit(_client_ip(request))
        except TrackingRateLimitExceeded:
            response = Response(status=status.HTTP_429_TOO_MANY_REQUESTS)
            response["Retry-After"] = str(settings.TRACKING_LOOKUP_IP_WINDOW_SECONDS)
            return response

        application = lookup_by_tracking_code(tracking_code)
        if application is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(ApplicationPublicDetailSerializer(application).data)


class StaffApplicationAssignmentView(APIView):
    """PATCH /api/v1/staff/applications/{id}/assignments — فقط hr_manager (T020a، FR-041)."""

    permission_classes = [IsHrManager]

    def patch(self, request, pk):
        application = get_object_or_404(Application, id=pk)
        serializer = AssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reviewer_id = serializer.validated_data["reviewer_id"]

        if reviewer_id is None:
            revoke_reviewer(application=application, revoked_by=request.user)
            return Response(status=status.HTTP_200_OK)

        reviewer = get_object_or_404(StaffUser, id=reviewer_id)

        try:
            assign_reviewer(application=application, reviewer=reviewer, assigned_by=request.user)
        except PermissionDenied as exc:
            return Response(
                {"code": "conflict", "message": str(exc), "field_errors": None, "request_id": ""},
                status=status.HTTP_409_CONFLICT,
            )
        except AssignmentConflict:
            return Response(
                {
                    "code": "conflict",
                    "message": "ارجاع دیگری هم‌زمان روی این پرونده ثبت شد؛ صفحه را تازه‌سازی کنید.",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_200_OK)


class StaffApplicationListView(ListAPIView):
    """
    GET /api/v1/staff/applications (T043، FR-022 تا FR-024). دامنه مجوز با
    `get_applications_queryset` اعمال می‌شود (پیش‌فرض منع)؛ فیلتر/جست‌وجو با همان تابعی که
    `StaffApplicationMetricsView` استفاده می‌کند تا دامنه آمار و فهرست دقیقاً یکسان بماند.
    هیچ `select_related`/`prefetch_related` روی `AttachmentContent` انجام نمی‌شود — محتوای
    باینری رزومه هرگز در این پرس‌وجو واکشی نمی‌شود (اصل I، FR-050).
    """

    permission_classes = [IsStaff]
    serializer_class = ApplicationStaffListSerializer

    def get_queryset(self):
        base = get_applications_queryset(self.request.user).select_related("job_position")
        filtered = apply_staff_filters(base, self.request.query_params)
        return filtered.order_by("-created_at", "id")


class StaffApplicationMetricsView(APIView):
    """GET /api/v1/staff/applications/metrics — همان دامنه/فیلتر فهرست (T043، FR-024)."""

    permission_classes = [IsStaff]

    def get(self, request):
        base = get_applications_queryset(request.user)
        filtered = apply_staff_filters(base, request.query_params)
        by_status = dict(filtered.values("status").annotate(total=Count("id")).values_list("status", "total"))
        return Response({"total": filtered.count(), "by_status": by_status})


class StaffApplicationDetailView(RetrieveAPIView):
    """GET /api/v1/staff/applications/{id} — جزئیات کامل در دامنه مجوز (T044)."""

    permission_classes = [IsStaff]
    serializer_class = ApplicationStaffDetailSerializer
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return get_applications_queryset(self.request.user).select_related("job_position", "candidate")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["allowed_queryset"] = get_applications_queryset(self.request.user)
        return context


class StaffResumeDownloadView(APIView):
    """
    GET /api/v1/staff/applications/{id}/resume (T044، FR-025). کنترل مجوز رکورد و وضعیت
    اسکن در *هر* درخواست دوباره بررسی می‌شود (نه فقط در لحظه ارجاع)؛ هیچ لینک عمومی/امضاشده
    مستقل صادر نمی‌شود — این تنها مسیر دانلود است. پاسخ بدون کش است و رویداد `resume_download`
    حسابرسی می‌شود.
    """

    permission_classes = [IsStaff]

    def get(self, request, pk):
        application = get_object_or_404(get_applications_queryset(request.user), id=pk)
        attachment = getattr(application, "resume", None)
        if attachment is None or not attachment.is_downloadable:
            # قرنطینه/scan_failed/pending/rejected هرگز قابل دانلود نیست؛ ۴۰۴ ساده.
            return Response(status=status.HTTP_404_NOT_FOUND)

        content = AttachmentContent.objects.get(attachment=attachment).data
        record_event(
            action="resume_download",
            staff_actor=request.user,
            object_type="Application",
            object_id=str(application.id),
        )

        safe_name = attachment.original_filename.replace('"', "").replace("\r", "").replace("\n", "")
        response = HttpResponse(bytes(content), content_type="application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class StaffApplicationNoteCreateView(APIView):
    """
    POST /api/v1/staff/applications/{id}/notes (T049، FR-026). دسترسی رکوردی با همان
    `get_applications_queryset` کنترل می‌شود — کارمندی که ارجاع فعال ندارد (یا ارجاعش لغو
    شده) ۴۰۴ می‌گیرد، حتی اگر نقشش عموماً اجازه یادداشت‌نویسی داشته باشد (الزام ۶).
    """

    permission_classes = [IsStaff]

    def post(self, request, pk):
        application = get_object_or_404(get_applications_queryset(request.user), id=pk)
        serializer = NoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        note = add_note(application=application, author=request.user, body=serializer.validated_data["body"])
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class StaffApplicationStatusView(APIView):
    """
    PATCH /api/v1/staff/applications/{id}/status (T050، FR-027 تا FR-031). دسترسی رکوردی با
    `get_applications_queryset` کنترل می‌شود؛ لغو ارجاع، امکان این مسیر را در درخواست بعدی
    برای همان کارمند قطع می‌کند (الزام ۶)، چون دیگر در آن queryset نیست.
    """

    permission_classes = [IsStaff]

    def patch(self, request, pk):
        application = get_object_or_404(get_applications_queryset(request.user), id=pk)
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = change_status(
                application_id=application.id,
                changed_by=request.user,
                expected_version=serializer.validated_data["expected_version"],
                to_status=serializer.validated_data["to_status"],
                reason=serializer.validated_data.get("reason", ""),
            )
        except VersionConflict:
            return Response(
                {
                    "code": "conflict",
                    "message": "این پرونده توسط کاربر دیگری تغییر کرده؛ لطفاً تازه‌سازی کنید.",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except InvalidTransition:
            return Response(
                {"code": "validation_error", "message": "این انتقال وضعیت مجاز نیست.", "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ReasonRequired:
            return Response(
                {"code": "validation_error", "message": "ثبت دلیل داخلی برای این تغییر اجباری است.", "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied as exc:
            return Response(
                {"code": "forbidden", "message": str(exc), "field_errors": None, "request_id": ""},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(ApplicationStaffDetailSerializer(updated, context={"request": request}).data)
