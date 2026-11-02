"""نرمال‌سازی متن مشترک: ارقام فارسی/عربی، پیشوند موبایل، حروف عربی/فارسی (FR-004)."""
import re

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_ARABIC_LETTER_MAP = str.maketrans({"ي": "ی", "ك": "ک"})


def normalize_digits(value: str) -> str:
    return value.translate(_DIGIT_MAP)


def normalize_mobile(value: str) -> str:
    """تبدیل به قالب استاندارد 09xxxxxxxxx؛ پذیرش ارقام فارسی/عربی و پیشوند +98/0098."""
    value = normalize_digits(value or "").strip()
    value = re.sub(r"\s|-", "", value)
    if value.startswith("+98"):
        value = "0" + value[3:]
    elif value.startswith("0098"):
        value = "0" + value[4:]
    elif value.startswith("98") and len(value) == 12:
        value = "0" + value[2:]
    return value


def normalize_persian_text(value: str) -> str:
    """یکسان‌سازی گونه‌های حروف فارسی/عربی برای جست‌وجوی سازگار (مثل شهر)."""
    value = normalize_digits(value or "")
    value = value.translate(_ARABIC_LETTER_MAP)
    return " ".join(value.strip().split())
