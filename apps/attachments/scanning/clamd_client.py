"""پیاده‌سازی ScannerClient با ClamAV از طریق پروتکل clamd (research.md §۴)."""
import io
import logging

from django.conf import settings

from .base import ScanResult, ScannerClient

logger = logging.getLogger("apps.attachments.scanning")


class ScannerUnavailable(Exception):
    """اسکنر قطع‌شده است؛ باید به pending/scan_failed ترجمه شود، نه clean (FR-010)."""


class ClamdScannerClient(ScannerClient):
    def scan(self, content: bytes) -> ScanResult:
        try:
            import clamd
        except ImportError as exc:  # pragma: no cover - فقط در محیط بدون پکیج clamd
            raise ScannerUnavailable("کتابخانه clamd نصب نیست") from exc

        try:
            client = clamd.ClamdNetworkSocket(host=settings.CLAMD_HOST, port=settings.CLAMD_PORT)
            result = client.instream(io.BytesIO(content))
        except Exception as exc:  # noqa: BLE001 - قطعی شبکه/سرویس باید scan_failed شود
            logger.warning("ClamAV unavailable: %s", exc)
            raise ScannerUnavailable(str(exc)) from exc

        status, reason = result.get("stream", ("ERROR", "unknown"))
        return ScanResult(clean=(status == "OK"), reason=reason or "")
