from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsHrManager

from ..models import JobPosition
from ..services import InvalidJobTransition, change_job_status, create_job, update_job
from .serializers import (
    JobPositionCreateSerializer,
    JobPositionPublicSerializer,
    JobPositionStaffSerializer,
    JobPositionUpdateSerializer,
    JobStatusChangeSerializer,
)


class PublicJobListView(ListAPIView):
    """
    GET /api/v1/jobs — فقط موقعیت‌های `open`، بدون نیاز به ورود (FR-001, FR-002, FR-039a).
    `draft` و `closed` هرگز دیده نمی‌شوند.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = JobPositionPublicSerializer
    pagination_class = None

    def get_queryset(self):
        return JobPosition.objects.filter(status=JobPosition.Status.OPEN)


class StaffJobListCreateView(APIView):
    """
    GET/POST /api/v1/staff/jobs (T060، FR-038/FR-039a). فقط `hr_manager` — فهرست کامل همه
    وضعیت‌ها؛ ایجاد موقعیت جدید همیشه در وضعیت `draft` (فعال‌سازی نیازمند انتقال صریح).
    """

    permission_classes = [IsHrManager]
    pagination_class = None

    def get(self, request):
        jobs = JobPosition.objects.all().order_by("-created_at")
        return Response(JobPositionStaffSerializer(jobs, many=True).data)

    def post(self, request):
        serializer = JobPositionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = create_job(created_by=request.user, **serializer.validated_data)
        return Response(JobPositionStaffSerializer(job).data, status=status.HTTP_201_CREATED)


class StaffJobDetailView(APIView):
    """PATCH /api/v1/staff/jobs/{id} — فیلدهای توصیفی فقط (T060). بدون DELETE (FR-038)."""

    permission_classes = [IsHrManager]

    def patch(self, request, pk):
        get_object_or_404(JobPosition, id=pk)
        serializer = JobPositionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            return Response(
                {"code": "validation_error", "message": "هیچ فیلدی برای ویرایش ارسال نشده.", "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job = update_job(job_id=pk, updated_by=request.user, **serializer.validated_data)
        return Response(JobPositionStaffSerializer(job).data)


class StaffJobStatusView(APIView):
    """
    PATCH /api/v1/staff/jobs/{id}/status (T060a، FR-039a). فقط `hr_manager`؛ چرخه
    `draft→open`، `open→closed`، `closed→open`؛ ورود به `open` = بازگشایی/فعال‌سازی حسابرسی‌شده.
    """

    permission_classes = [IsHrManager]

    def patch(self, request, pk):
        get_object_or_404(JobPosition, id=pk)
        serializer = JobStatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            job = change_job_status(
                job_id=pk, changed_by=request.user, to_status=serializer.validated_data["status"]
            )
        except InvalidJobTransition as exc:
            return Response(
                {"code": "validation_error", "message": str(exc), "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied as exc:
            return Response(
                {"code": "forbidden", "message": str(exc), "field_errors": None, "request_id": ""},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(JobPositionStaffSerializer(job).data)
