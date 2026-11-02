"""
T087: جریان واقعی مرورگری US7 — مدیر HR وارد می‌شود، صفحهٔ مدیریت کاربران را باز می‌کند،
حساب کارشناس جذب تازه می‌سازد، همان حساب بلافاصله با نام‌کاربری/رمز عبور وارد می‌شود (بدون
عامل دوم — اصل V نسخهٔ ۳.۰.۰)، سپس مدیر HR آن را غیرفعال می‌کند و دسترسی بعدی همان حساب
بلافاصله قطع می‌شود (FR-021a تا FR-021d).
"""
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.django_db(transaction=True)


def _login(page, live_server, username: str, password: str):
    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("#login-button")
    page.wait_for_url("**/staff/dashboard")


def test_hr_manager_creates_account_new_user_logs_in_then_gets_deactivated(
    live_server, page, browser, hr_manager
):
    hr_manager.set_password("a-strong-password-123")
    hr_manager.save(update_fields=["password"])

    _login(page, live_server, hr_manager.username, "a-strong-password-123")

    page.goto(f"{live_server.url}/staff/users")
    page.fill("#user-username", "us7_browser_recruiter")
    page.fill("#user-password", "AnotherStr0ngPass!")
    page.select_option("#user-role", "recruiter")
    page.click("#create-user-submit")

    result = page.locator("#create-user-result")
    expect(result).to_be_visible(timeout=10000)
    expect(result).to_contain_text("بلافاصله با همین نام‌کاربری/رمز عبور قابل ورود است")

    # سطر حساب تازه باید در فهرست دیده شود.
    expect(page.locator("#users-rows")).to_contain_text("us7_browser_recruiter")

    # اولین ورود واقعی حساب تازه — تک‌مرحله‌ای، بدون عامل دوم.
    new_user_context = browser.new_context()
    new_user_page = new_user_context.new_page()
    _login(new_user_page, live_server, "us7_browser_recruiter", "AnotherStr0ngPass!")

    # مدیر HR اکنون همان حساب را غیرفعال می‌کند.
    page.goto(f"{live_server.url}/staff/users")
    row = page.locator("#users-rows tr", has_text="us7_browser_recruiter")
    row.get_by_role("button", name="غیرفعال‌سازی").click()
    expect(row).to_contain_text("غیرفعال")

    # درخواست بعدی همان حساب (بدون خروج/ورود دوباره) باید رد شود.
    new_user_page.goto(f"{live_server.url}/staff/dashboard")
    api_resp = new_user_page.request.get(f"{live_server.url}/api/v1/staff/applications")
    assert api_resp.status in (401, 403)
