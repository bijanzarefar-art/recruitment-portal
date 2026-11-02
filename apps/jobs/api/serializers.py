from rest_framework import serializers

from ..models import JobPosition


class JobPositionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosition
        fields = ["id", "title", "department", "location", "requirements"]


class JobPositionStaffSerializer(JobPositionPublicSerializer):
    class Meta(JobPositionPublicSerializer.Meta):
        fields = JobPositionPublicSerializer.Meta.fields + ["status", "created_at"]


class JobPositionCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    department = serializers.CharField(max_length=200, required=False, allow_blank=True)
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    requirements = serializers.CharField(required=False, allow_blank=True)


class JobPositionUpdateSerializer(serializers.Serializer):
    """فیلدهای توصیفی فقط — تغییر وضعیت از مسیر جداگانه `PATCH .../status` (FR-039a)."""

    title = serializers.CharField(max_length=200, trim_whitespace=True, required=False)
    department = serializers.CharField(max_length=200, required=False, allow_blank=True)
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    requirements = serializers.CharField(required=False, allow_blank=True)


class JobStatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=JobPosition.Status.choices)
