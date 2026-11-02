from rest_framework import serializers

from ..models import Application, PrivacyNotice


class PrivacyNoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyNotice
        fields = ["version", "body"]


class ApplicationCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100, trim_whitespace=True)
    last_name = serializers.CharField(max_length=100, trim_whitespace=True)
    mobile = serializers.CharField(max_length=20)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    job_position = serializers.UUIDField()
    employment = serializers.ChoiceField(choices=Application.Employment.choices)
    experience = serializers.ChoiceField(choices=Application.Experience.choices)
    availability = serializers.ChoiceField(choices=Application.Availability.choices)
    last_title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    last_company = serializers.CharField(max_length=200, required=False, allow_blank=True)
    resume_upload_id = serializers.UUIDField()
    privacy_notice_version = serializers.CharField()
    consent = serializers.BooleanField()

    def validate(self, attrs):
        if attrs["experience"] != Application.Experience.NO_EXPERIENCE:
            if not attrs.get("last_title") or not attrs.get("last_company"):
                raise serializers.ValidationError(
                    {"last_title": ["آخرین عنوان شغلی و شرکت برای این سابقه کاری اجباری است."]}
                )
        if not attrs.get("consent"):
            raise serializers.ValidationError({"consent": ["پذیرش متن حریم خصوصی اجباری است."]})
        return attrs


class ApplicationReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["tracking_code", "status", "created_at"]


class ApplicationPublicDetailSerializer(serializers.ModelSerializer):
    job_position = serializers.CharField(source="job_position.title")

    class Meta:
        model = Application
        fields = ["tracking_code", "job_position", "status", "updated_at"]


class AssignmentSerializer(serializers.Serializer):
    reviewer_id = serializers.UUIDField(allow_null=True)


class NoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=1, max_length=5000, trim_whitespace=True)


class NoteSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    author = serializers.CharField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()


class StatusChangeSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Application.Status.choices)
    expected_version = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class StaffReviewerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    role = serializers.CharField()


class ApplicationStaffListSerializer(serializers.ModelSerializer):
    """
    فهرست پرونده‌ها برای کارکنان (T043، FR-022 تا FR-024). عمداً فاقد فیلد `resume`/محتوای
    باینری است — پرس‌وجوی فهرست هرگز AttachmentContent را واکشی نمی‌کند (اصل I، FR-050).
    """

    job_position = serializers.CharField(source="job_position.title")
    job_position_id = serializers.UUIDField(source="job_position.id")

    class Meta:
        model = Application
        fields = [
            "id",
            "tracking_code",
            "first_name",
            "last_name",
            "mobile_snapshot",
            "city",
            "job_position",
            "job_position_id",
            "status",
            "experience",
            "created_at",
            "updated_at",
        ]


class ApplicationStaffDetailSerializer(serializers.ModelSerializer):
    job_position = serializers.CharField(source="job_position.title")
    reviewer = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()
    previous_applications = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "tracking_code",
            "first_name",
            "last_name",
            "mobile_snapshot",
            "email",
            "city",
            "job_position",
            "employment",
            "experience",
            "availability",
            "last_title",
            "last_company",
            "status",
            "version",
            "reviewer",
            "notes",
            "status_history",
            "previous_applications",
            "created_at",
            "updated_at",
        ]

    def get_reviewer(self, obj):
        active = obj.reviewer_assignments.filter(revoked_at__isnull=True).select_related("reviewer").first()
        if not active:
            return None
        return {"id": str(active.reviewer_id), "role": active.reviewer_role_at_assignment}

    def get_notes(self, obj):
        return [
            {"id": str(n.id), "author": n.author.username, "body": n.body, "created_at": n.created_at}
            for n in obj.notes.select_related("author").all()
        ]

    def get_status_history(self, obj):
        return [
            {"from_status": h.from_status, "to_status": h.to_status, "created_at": h.created_at}
            for h in obj.status_history.all()
        ]

    def get_previous_applications(self, obj):
        """
        اشاره خلاصه به پرونده‌های قبلی همین متقاضی، فقط در دامنه مجوز کاربر جاری (FR-063).
        فیلتر دامنه توسط view (با همان get_applications_queryset) اعمال می‌شود، نه اینجا.
        """
        request = self.context.get("request")
        allowed_queryset = self.context.get("allowed_queryset")
        if request is None or allowed_queryset is None:
            return []
        others = allowed_queryset.filter(candidate=obj.candidate).exclude(id=obj.id)
        return [
            {"id": str(a.id), "job_position": a.job_position.title, "status": a.status} for a in others
        ]
