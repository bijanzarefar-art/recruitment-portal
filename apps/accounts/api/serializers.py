from rest_framework import serializers

from ..models import StaffUser


class StaffLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


ADMIN_ASSIGNABLE_ROLES = (
    StaffUser.Role.RECRUITER,
    StaffUser.Role.HIRING_MANAGER,
    StaffUser.Role.HR_MANAGER,
)


class StaffAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffUser
        fields = ["id", "username", "role", "is_active", "created_at"]


class StaffAccountCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False, min_length=8)
    role = serializers.ChoiceField(choices=[r.value for r in ADMIN_ASSIGNABLE_ROLES])


class StaffAccountUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[r.value for r in ADMIN_ASSIGNABLE_ROLES], required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("حداقل یکی از role یا is_active باید ارسال شود.")
        return attrs
