// صفحهٔ «حساب من»: هر کارمند رمز خودش را عوض می‌کند. رمز فعلی برای احراز مجدد الزامی است
// (سمت سرور هم دوباره بررسی می‌شود — این فقط بازخورد سریع است، نه کنترل امنیتی).
import { apiFetch } from "./csrf.js";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("change-password-form");
    if (!form) return;

    const errorEl = document.querySelector('[data-error-for="password"]');
    const successEl = document.getElementById("password-success");
    const submitBtn = document.getElementById("change-password-submit");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl.textContent = "";
        successEl.hidden = true;

        const oldPassword = document.getElementById("old-password").value;
        const newPassword = document.getElementById("new-password").value;
        const confirmPassword = document.getElementById("confirm-password").value;

        if (newPassword !== confirmPassword) {
            errorEl.textContent = "رمز جدید و تکرار آن یکسان نیستند.";
            errorEl.focus();
            return;
        }

        submitBtn.disabled = true;
        try {
            const response = await apiFetch("/api/v1/auth/staff/change-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
            });

            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                errorEl.textContent = payload.message || "تغییر رمز ناموفق بود.";
                errorEl.focus();
                return;
            }

            form.reset();
            successEl.textContent = payload.message || "رمز عبور با موفقیت تغییر کرد.";
            successEl.hidden = false;
        } catch (err) {
            errorEl.textContent = "خطای ارتباط با سرور؛ دوباره تلاش کنید.";
            errorEl.focus();
        } finally {
            submitBtn.disabled = false;
        }
    });
});
