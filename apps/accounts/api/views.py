from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_event

from ..models import StaffUser
from ..permissions import IsHrManager
from ..services import (
    CannotDeactivateSelf,
    DuplicateUsername,
    LastActiveHrManager,
    StaffLoginRateLimitExceeded,
    change_staff_role,
    create_staff_account,
    enforce_staff_login_rate_limit,
    set_staff_active,
)
from .serializers import (
    StaffAccountCreateSerializer,
    StaffAccountSerializer,
    StaffAccountUpdateSerializer,
    StaffLoginSerializer,
)


def _check_rate_limit(request, username: str):
    """
    FR-047: پیش از هر تلاش احراز هویت (رمزی یا MFA) شمارش می‌شود، تا هیچ مسیری برای
    دورزدن محدودیت از راه جایگزین نباشد. پاسخ ۴۲۹ همراه `Retry-After` برمی‌گرداند یا None.
    """
    try:
        enforce_staff_login_rate_limit(username=username, request=request)
    except StaffLoginRateLimitExceeded as exc:
        response = Response(
            {"detail": "تعداد تلاش‌های ورود بیش از حد مجاز است؛ کمی بعد دوباره تلاش کنید."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = str(exc.retry_after_seconds)
        return response
    return None


class StaffLoginView(APIView):
    """
    POST /api/v1/auth/staff/login — تکمیل ورود کارمند با نام‌کاربری/رمز عبور (FR-017, FR-047).
    اصل V نسخهٔ ۳.۰.۰: هیچ عامل دومی وجود ندارد؛ نشست بلافاصله پس از تأیید رمز صادر می‌شود.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        limited = _check_rate_limit(request, serializer.validated_data["username"])
        if limited is not None:
            return limited

        user = authenticate(
            request, username=serializer.validated_data["username"], password=serializer.validated_data["password"]
        )
        if user is None or not user.is_active:
            return Response({"detail": "نام کاربری یا رمز عبور نادرست است."}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)
        record_event(action="staff_login", staff_actor=user, object_type="StaffUser", object_id=str(user.id))
        return Response(status=status.HTTP_200_OK)


class StaffLogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffUserListCreateView(APIView):
    """
    GET/POST /api/v1/staff/users — مدیریت کاربران از پنل (US7، FR-021a). فقط `hr_manager`.
    فهرست بدون صفحه‌بندی DRF (یک آرایهٔ ساده)، هم‌سو با الگوی `GET /api/v1/staff/jobs`.
    """

    permission_classes = [IsHrManager]

    def get(self, request):
        users = StaffUser.objects.order_by("-created_at")
        return Response(StaffAccountSerializer(users, many=True).data)

    def post(self, request):
        serializer = StaffAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = create_staff_account(
                created_by=request.user,
                username=serializer.validated_data["username"],
                password=serializer.validated_data["password"],
                role=serializer.validated_data["role"],
            )
        except DuplicateUsername:
            return Response(
                {"code": "validation_error", "message": "این نام کاربری از قبل وجود دارد.", "field_errors": None, "request_id": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(StaffAccountSerializer(user).data, status=status.HTTP_201_CREATED)


class StaffUserDetailView(APIView):
    """PATCH /api/v1/staff/users/{id} — تغییر نقش و/یا وضعیت فعال‌بودن (US7، FR-021a تا FR-021c)."""

    permission_classes = [IsHrManager]

    def patch(self, request, pk):
        get_object_or_404(StaffUser, id=pk)  # 404 زودهنگام برای شناسهٔ ناموجود
        serializer = StaffAccountUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        try:
            if "role" in validated:
                change_staff_role(changed_by=request.user, target_id=pk, new_role=validated["role"])
            if "is_active" in validated:
                set_staff_active(changed_by=request.user, target_id=pk, is_active=validated["is_active"])
        except CannotDeactivateSelf:
            return Response(
                {"code": "forbidden", "message": "امکان غیرفعال‌کردن حساب خودتان وجود ندارد.", "field_errors": None, "request_id": ""},
                status=status.HTTP_403_FORBIDDEN,
            )
        except LastActiveHrManager:
            return Response(
                {
                    "code": "forbidden",
                    "message": "نمی‌توان آخرین مدیر HR فعال را غیرفعال کرد.",
                    "field_errors": None,
                    "request_id": "",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        updated = StaffUser.objects.get(id=pk)
        return Response(StaffAccountSerializer(updated).data)
