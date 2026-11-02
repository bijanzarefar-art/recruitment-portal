from rest_framework import serializers

from ..models import Attachment


class UploadStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "scan_status", "original_filename"]
