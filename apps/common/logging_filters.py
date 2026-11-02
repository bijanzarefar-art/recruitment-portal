import logging
import re

_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)otp[_ ]?code\s*=\s*\S+"),
    re.compile(r"(?i)password\s*=\s*\S+"),
    re.compile(r"(?i)authorization:\s*\S+"),
)


class RedactSensitiveDataFilter(logging.Filter):
    """حذف داده حساس (OTP خام، رمز عبور) از لاگ‌ها (FR-055، اصل VIII)."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in _SENSITIVE_PATTERNS:
            message = pattern.sub(lambda m: m.group(0).split("=")[0] + "=[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True
