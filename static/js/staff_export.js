// صفحه خروجی‌گیری (T057)؛ مجوز واقعی و اعتبارسنجی ستون/سقف فقط در سرور انجام می‌شود.
import { apiFetch } from "./csrf.js";

const COLUMNS = [
    ["tracking_code", "کد پیگیری"],
    ["first_name", "نام"],
    ["last_name", "نام خانوادگی"],
    ["mobile_snapshot", "موبایل"],
    ["email", "ایمیل"],
    ["city", "شهر"],
    ["job_position_title", "موقعیت شغلی"],
    ["employment", "وضعیت اشتغال"],
    ["experience", "سابقه کاری"],
    ["availability", "امکان شروع"],
    ["last_title", "آخرین عنوان شغلی"],
    ["last_company", "آخرین شرکت"],
    ["status", "وضعیت"],
    ["created_at", "تاریخ ثبت"],
    ["updated_at", "آخرین به‌روزرسانی"],
];

function renderColumnCheckboxes() {
    const container = document.getElementById("column-checkboxes");
    COLUMNS.forEach(([key, label]) => {
        const wrapper = document.createElement("label");
        wrapper.style.display = "flex";
        wrapper.style.gap = "6px";
        wrapper.style.alignItems = "center";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = key;
        checkbox.checked = true;
        checkbox.name = "columns";
        wrapper.appendChild(checkbox);
        wrapper.appendChild(document.createTextNode(label));
        container.appendChild(wrapper);
    });
}

function filenameFromDisposition(disposition, fallback) {
    if (!disposition) return fallback;
    const match = disposition.match(/filename="?([^"]+)"?/);
    return match ? match[1] : fallback;
}

document.addEventListener("DOMContentLoaded", () => {
    renderColumnCheckboxes();

    document.getElementById("export-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorEl = document.getElementById("export-error");
        const noticeEl = document.getElementById("export-notice");
        errorEl.textContent = "";
        noticeEl.hidden = true;

        const format = document.getElementById("export-format").value;
        const status = document.getElementById("export-status").value;
        const city = document.getElementById("export-city").value;
        const q = document.getElementById("export-q").value;
        const columns = Array.from(document.querySelectorAll('input[name="columns"]:checked')).map((el) => el.value);

        const resp = await apiFetch("/api/v1/staff/exports", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ format, status, city, q, columns }),
        });

        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            errorEl.textContent = payload.message || "خروجی‌گیری ناموفق بود.";
            return;
        }

        const disposition = resp.headers.get("Content-Disposition");
        const fallbackName = format === "xlsx" ? "applications_export.xlsx" : "applications_export.csv";
        const filename = filenameFromDisposition(disposition, fallbackName);

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        if (format === "csv") {
            noticeEl.hidden = false;
        }
    });
});
