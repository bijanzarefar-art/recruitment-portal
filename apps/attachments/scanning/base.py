"""رابط اسکنر بدافزار قابل‌تعویض (research.md §۴، اصل VI)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass
class ScanResult:
    clean: bool
    reason: str = ""


class ScannerClient(ABC):
    @abstractmethod
    def scan(self, content: bytes) -> ScanResult:
        ...


def get_scanner_client() -> ScannerClient:
    backend_cls = import_string(settings.SCANNER_BACKEND)
    return backend_cls()
