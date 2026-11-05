// ورود کارمند: نام‌کاربری + رمز عبور → هدایت به داشبورد یا صفحهٔ درخواستی قبلی (اصل V نسخهٔ
// ۳.۰.۰ — بدون عامل دوم). `next` فقط وقتی معتبر است که مسیر داخلی `/staff/...` باشد؛ در غیر
// این صورت نادیده گرفته می‌شود تا باز-هدایت باز (open redirect) ممکن نشود.
import { apiFetch } from "./csrf.js";

function safeNextPath() {
    const next = new URLSearchParams(window.location.search).get("next");
    if (next && next.startsWith("/staff/") && !next.startsWith("//") && !next.includes("://")) {
        return next;
    }
    return "/staff/dashboard";
}

document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    const loginButton = document.getElementById("login-button");

    // فرم: Enter در فیلد نام کاربری یا رمز هم ورود را اجرا می‌کند (WCAG 2.1.1 Keyboard).
    const submitLogin = async () => {
        const username = document.getElementById("username").value;
        const password = document.getElementById("password").value;
        const errorEl = document.querySelector('[data-error-for="login"]');
        errorEl.textContent = "";

        const response = await apiFetch("/api/v1/auth/staff/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });

        if (!response.ok) {
            errorEl.textContent = "نام کاربری یا رمز عبور نادرست است.";
            errorEl.focus();
            return;
        }

        window.location.href = safeNextPath();
    };

    if (loginForm) {
        loginForm.addEventListener("submit", (event) => {
            event.preventDefault();
            submitLogin();
        });
    } else {
        loginButton.addEventListener("click", submitLogin);
    }
});
