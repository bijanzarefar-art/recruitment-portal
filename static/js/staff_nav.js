// دکمهٔ خروج در نوار کارکنان؛ نشست سمت سرور را باطل می‌کند (POST /api/v1/auth/staff/logout) و
// به دروازهٔ ورودی پورتال («/») برمی‌گردد، نه مستقیم به فرم ورود.
import { apiFetch } from "./csrf.js";

document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("logout-button");
    if (!button) return;
    button.addEventListener("click", async () => {
        button.disabled = true;
        await apiFetch("/api/v1/auth/staff/logout", { method: "POST" });
        window.location.href = "/";
    });
});
