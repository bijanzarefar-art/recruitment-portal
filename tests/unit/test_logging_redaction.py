"""T063: لاگ ساختاریافته نباید OTP خام/رمز/هدر مجوز را ثبت کند (FR-055، اصل VIII)."""
import logging

from apps.common.logging_filters import RedactSensitiveDataFilter


def _filtered_message(message: str) -> str:
    record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg=message, args=(), exc_info=None)
    RedactSensitiveDataFilter().filter(record)
    return record.getMessage()


def test_otp_code_is_redacted():
    assert "123456" not in _filtered_message("sending otp_code=123456 to candidate")


def test_password_is_redacted():
    assert "hunter2" not in _filtered_message("login attempt password=hunter2 username=ali")


def test_authorization_header_is_redacted():
    assert "Bearer abc.def" not in _filtered_message("request headers authorization: Bearer abc.def")


def test_non_sensitive_message_is_unchanged():
    assert _filtered_message("application submitted") == "application submitted"
