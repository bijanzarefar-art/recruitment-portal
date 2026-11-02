from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Attachment
from ..services import create_upload
from ..validators import InvalidResumeFile, ResumeTooLarge
from .serializers import UploadStatusSerializer


class CandidateUploadView(APIView):
    """
    POST /api/v1/candidate/uploads — بارگذاری موقت بدون احراز هویت (اصل V نسخهٔ ۲.۰.۰؛
    FR-049, FR-052). تنها مکانیزم کنترل دسترسی، هدر اجباری `X-Upload-Attempt-Key` است
    (FR-051) — کلاینت این مقدار را یک‌بار در لحظهٔ بازشدن فرم تولید می‌کند و هم در بارگذاری
    فایل و هم در ارسال نهایی فرم ارسال می‌کند.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response(
                {"code": "validation_error", "message": "فایل ارسال نشده است.", "field_errors": None, "request_id": ""},
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

        content = uploaded_file.read()

        try:
            attachment = create_upload(
                upload_attempt_key=upload_attempt_key,
                original_filename=uploaded_file.name,
                content=content,
            )
        except ResumeTooLarge as exc:
            return Response(
                {"code": "validation_error", "message": str(exc), "field_errors": None, "request_id": ""},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        except InvalidResumeFile as exc:
            return Response(
                {"code": "validation_error", "message": str(exc), "field_errors": None, "request_id": ""},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        return Response(UploadStatusSerializer(attachment).data, status=status.HTTP_201_CREATED)


class CandidateUploadStatusView(APIView):
    """
    GET /api/v1/candidate/uploads/{id} — وضعیت اسکن. دسترسی با همان `X-Upload-Attempt-Key`
    کنترل می‌شود که در بارگذاری استفاده شد؛ بدون آن یا با کلید نادرست ۴۰۴ (بدون افشای وجود
    رکورد برای تلاش دیگر).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, pk):
        upload_attempt_key = request.headers.get("X-Upload-Attempt-Key", "")
        attachment = get_object_or_404(Attachment, id=pk, upload_attempt_key=upload_attempt_key)
        return Response(UploadStatusSerializer(attachment).data)
