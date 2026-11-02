"""
T054: سیاست ستون‌های مجاز خروجی، خنثی‌سازی فرمول، قالب متنی صفر ابتدایی و سقف ردیف (FR-032 تا
FR-035، SC-006). بدون نیاز به دیتابیس: مستقیماً روی `export_policy`/`services` تست می‌شود.
"""
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from apps.reporting.export_policy import (
    ALLOWED_COLUMNS,
    MAX_EXPORT_ROWS,
    InvalidColumns,
    TooManyRows,
    neutralize_formula,
    validate_columns,
)
from apps.reporting.services import collect_rows, render_csv, render_xlsx


def test_notes_and_audit_fields_are_not_in_allowed_columns_at_all():
    """FR-033: یادداشت و داده حسابرسی اصلاً نباید در فهرست ستون‌های قابل‌خروجی وجود داشته باشند."""
    forbidden = {"notes", "internal_reason", "audit", "status_history", "reviewer", "resume", "password"}
    assert forbidden.isdisjoint(ALLOWED_COLUMNS.keys())


def test_default_columns_exclude_nothing_sensitive():
    columns = validate_columns(None)
    assert set(columns) == set(ALLOWED_COLUMNS.keys())


def test_requesting_disallowed_column_is_rejected():
    with pytest.raises(InvalidColumns) as exc_info:
        validate_columns(["tracking_code", "notes", "password"])
    assert set(exc_info.value.invalid_keys) == {"notes", "password"}


@pytest.mark.parametrize(
    "raw,expected_prefixed",
    [
        ("=SUM(A1)", True),
        ("+1234", True),
        ("-1234", True),
        ("@SUM(A1)", True),
        ("   =cmd", True),  # فاصله ابتدایی
        ("\t+cmd", True),  # تب ابتدایی
        ("normal text", False),
        ("علی رضایی", False),
        (None, False),
    ],
)
def test_neutralize_formula_prefixes_dangerous_values_in_both_formats(raw, expected_prefixed):
    neutralized = neutralize_formula(raw)
    stripped = neutralized.lstrip(" \t\r\n\x0b\x0c")
    if expected_prefixed:
        assert stripped.startswith("'")
    else:
        assert neutralized == ("" if raw is None else raw)


def test_row_count_beyond_cap_is_rejected_without_building_file():
    rows = [SimpleNamespace(tracking_code=f"t{i}") for i in range(MAX_EXPORT_ROWS + 1)]
    with pytest.raises(TooManyRows):
        collect_rows(rows, ["tracking_code"])


def test_row_count_at_exactly_the_cap_is_accepted():
    rows = [SimpleNamespace(tracking_code=f"t{i}") for i in range(MAX_EXPORT_ROWS)]
    collected = collect_rows(rows, ["tracking_code"])
    assert len(collected) == MAX_EXPORT_ROWS


def test_csv_output_has_bom_and_neutralized_formula_value():
    rows = [["=cmd|calc"], ["نام عادی"]]
    content = render_csv(["first_name"], rows)
    assert content.startswith(b"\xef\xbb\xbf")
    text = content.decode("utf-8-sig")
    lines = text.splitlines()
    assert any(line.startswith("'=cmd|calc") for line in lines)
    assert not any(line.startswith("=cmd|calc") for line in lines)


def test_xlsx_output_neutralizes_formula_and_keeps_text_format_for_mobile_and_tracking_code():
    import io

    rows = [["0912000", "0098765", "=SUM(A1:A9)"]]
    content = render_xlsx(["mobile_snapshot", "tracking_code", "first_name"], rows)
    workbook = load_workbook(io.BytesIO(content))
    sheet = workbook.active

    header_row = next(sheet.iter_rows(min_row=1, max_row=1))
    assert [c.value for c in header_row] == [
        ALLOWED_COLUMNS["mobile_snapshot"],
        ALLOWED_COLUMNS["tracking_code"],
        ALLOWED_COLUMNS["first_name"],
    ]

    data_row = next(sheet.iter_rows(min_row=2, max_row=2))
    mobile_cell, tracking_cell, formula_cell = data_row

    # صفر ابتدایی حفظ شده (مقدار رشته‌ای دقیقاً همان است، نه عدد بدون صفر).
    assert mobile_cell.value == "0912000"
    assert tracking_cell.value == "0098765"
    assert mobile_cell.number_format == "@"
    assert tracking_cell.number_format == "@"

    # مقدار فرمول‌مانند خنثی شده.
    assert str(formula_cell.value).startswith("'")
