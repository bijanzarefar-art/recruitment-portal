"""
قید دیتابیس `octet_length(data) BETWEEN 1 AND 5242880` روی AttachmentContent.data
(data-model.md؛ FR-005). CheckConstraint استاندارد Django تابع octet_length
پورتال‌ناپذیر PostgreSQL را پشتیبانی نمی‌کند، پس با RunSQL اعمال می‌شود.
"""
from django.db import migrations

ADD_CONSTRAINT_SQL = """
ALTER TABLE attachments_attachmentcontent
ADD CONSTRAINT attachment_content_size_bytes_check
CHECK (octet_length(data) BETWEEN 1 AND 5242880);
"""

DROP_CONSTRAINT_SQL = """
ALTER TABLE attachments_attachmentcontent
DROP CONSTRAINT IF EXISTS attachment_content_size_bytes_check;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("attachments", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=ADD_CONSTRAINT_SQL, reverse_sql=DROP_CONSTRAINT_SQL),
    ]
