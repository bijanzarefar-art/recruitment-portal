import uuid

from django.db import models
from django.db.models import Q


class Application(models.Model):
    """
    رکورد اصلی هر درخواست؛ نسخه مستقل (snapshot) از اطلاعات فرم (FR-056). T009.
    """

    class Employment(models.TextChoices):
        FULL_TIME = "full_time", "تمام‌وقت"
        PART_TIME = "part_time", "پاره‌وقت"
        UNEMPLOYED = "unemployed", "بدون شغل"
        STUDENT = "student", "دانشجو"
        OTHER = "other", "سایر"

    class Experience(models.TextChoices):
        NO_EXPERIENCE = "no_experience", "بدون سابقه"
        UNDER_1 = "under_1", "کمتر از یک سال"
        YEARS_1_3 = "years_1_3", "یک تا سه سال"
        YEARS_3_5 = "years_3_5", "سه تا پنج سال"
        YEARS_5_10 = "years_5_10", "پنج تا ده سال"
        OVER_10 = "over_10", "بیش از ده سال"

    class Availability(models.TextChoices):
        IMMEDIATE = "immediate", "بلافاصله"
        WITHIN_2_WEEKS = "within_2_weeks", "حداکثر دو هفته"
        WEEKS_2_4 = "weeks_2_4", "دو تا چهار هفته"
        OVER_1_MONTH = "over_1_month", "بیش از یک ماه"

    class Status(models.TextChoices):
        NEW = "new", "در انتظار غربالگری اولیه"
        PHONE = "phone", "تماس اولیه انجام شد"
        INTERVIEW = "interview", "دعوت به مصاحبه"
        APPROVED = "approved", "تأیید اولیه"
        REJECTED = "rejected", "عدم ادامه فرآیند"
        HIRED = "hired", "استخدام شد"

    ACTIVE_STATUSES = (Status.NEW, Status.PHONE, Status.INTERVIEW, Status.APPROVED)
    FINAL_STATUSES = (Status.REJECTED, Status.HIRED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tracking_code = models.CharField(max_length=32, unique=True)
    candidate = models.ForeignKey("candidates.Candidate", on_delete=models.PROTECT, related_name="applications")
    job_position = models.ForeignKey("jobs.JobPosition", on_delete=models.PROTECT, related_name="applications")

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    mobile_snapshot = models.CharField(max_length=15)
    email = models.EmailField(max_length=254, blank=True)
    city = models.CharField(max_length=100)
    employment = models.CharField(max_length=20, choices=Employment.choices)
    experience = models.CharField(max_length=20, choices=Experience.choices)
    availability = models.CharField(max_length=20, choices=Availability.choices)
    last_title = models.CharField(max_length=200, blank=True)
    last_company = models.CharField(max_length=200, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    version = models.IntegerField(default=1)
    idempotency_key = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job_position"],
                condition=Q(status__in=["new", "phone", "interview", "approved"]),
                name="uniq_active_application_per_candidate_job",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at", "id"]),
            models.Index(fields=["job_position", "created_at", "id"]),
            models.Index(fields=["candidate"]),
        ]

    def __str__(self) -> str:
        return f"{self.tracking_code} ({self.get_status_display()})"


class ApplicationReviewer(models.Model):
    """
    ارجاع فعال پرونده؛ حداکثر یک رکورد فعال در هر لحظه برای هر Application (T010).
    ترتیب: اول recruiter، سپس جایگزینی با hiring_manager (رفع یافته C2، T020a).
    """

    class ReviewerRole(models.TextChoices):
        RECRUITER = "recruiter", "کارشناس جذب"
        HIRING_MANAGER = "hiring_manager", "مدیر استخدام"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="reviewer_assignments")
    reviewer = models.ForeignKey("accounts.StaffUser", on_delete=models.PROTECT, related_name="assigned_applications")
    reviewer_role_at_assignment = models.CharField(max_length=20, choices=ReviewerRole.choices)
    assigned_by = models.ForeignKey(
        "accounts.StaffUser", on_delete=models.PROTECT, related_name="assignments_made"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["application"],
                condition=Q(revoked_at__isnull=True),
                name="uniq_active_reviewer_per_application",
            ),
        ]
        indexes = [models.Index(fields=["reviewer", "revoked_at"])]


class ApplicationNote(models.Model):
    """یادداشت داخلی، بدون مسیر ویرایش معمول (FR-026). T011."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey("accounts.StaffUser", on_delete=models.PROTECT, related_name="+")
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class StatusHistory(models.Model):
    """ردیف غیرقابل‌تغییر هر انتقال وضعیت (FR-028, FR-030, FR-031). T012."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=10, choices=Application.Status.choices)
    to_status = models.CharField(max_length=10, choices=Application.Status.choices)
    changed_by = models.ForeignKey(
        "accounts.StaffUser", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    internal_reason = models.TextField(blank=True)
    is_exception = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PrivacyNotice(models.Model):
    """متن نسخه‌بندی‌شده حریم خصوصی/اجازه تماس (FR-004). T013."""

    version = models.CharField(max_length=32, unique=True)
    body = models.TextField()
    published_at = models.DateTimeField()

    def __str__(self) -> str:
        return self.version

    class Meta:
        ordering = ["-published_at"]


class Consent(models.Model):
    """پذیرش اجباری در لحظه ثبت، با زمان سرور (FR-004). T013."""

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="consent")
    privacy_notice = models.ForeignKey(PrivacyNotice, on_delete=models.PROTECT, related_name="+")
    accepted_at = models.DateTimeField()


class IdempotencyRecord(models.Model):
    """کلید تکرارپذیری ثبت درخواست (FR-009). T016."""

    candidate = models.ForeignKey("candidates.Candidate", on_delete=models.CASCADE, related_name="idempotency_records")
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["candidate", "idempotency_key"], name="uniq_candidate_idempotency_key")
        ]
