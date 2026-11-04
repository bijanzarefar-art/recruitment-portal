// پیگیری فقط با کد پیگیری — بدون هیچ مرحلهٔ OTP (اصل V نسخهٔ ۲.۰.۰، FR-012, FR-016, FR-043, FR-044).
import { apiFetch } from "./csrf.js";

const STATUS_LABELS = {
    new: "در انتظار غربالگری اولیه",
    phone: "تماس اولیه انجام شد",
    interview: "دعوت به مصاحبه",
    approved: "تأیید اولیه",
    rejected: "عدم ادامه فرآیند",
    hired: "استخدام شد",
};

// ترتیب مراحل، هم‌راستا با ماشین حالت سمت سرور (apps/applications/statemachine.py).
// «رد» و «استخدام» مرحلهٔ پایانی‌اند و جای هم نمی‌نشینند.
const PROGRESS_STEPS = ["new", "phone", "interview", "approved", "hired"];

function renderSteps(currentStatus) {
    const container = document.getElementById("result-steps");
    if (!container) return;
    container.innerHTML = "";

    const isRejected = currentStatus === "rejected";
    const reachedIndex = PROGRESS_STEPS.indexOf(currentStatus);

    PROGRESS_STEPS.forEach((status, index) => {
        const step = document.createElement("div");
        step.className = "track-step";

        // وقتی رد شده، مراحل تا قبل از «استخدام» گذشته‌اند ولی دیگر ادامه‌ای نیست؛
        // پس هیچ مرحله‌ای «فعال» نشان داده نمی‌شود و وضعیت رد جداگانه پایین می‌آید.
        if (!isRejected) {
            if (index < reachedIndex) step.classList.add("is-done");
            else if (index === reachedIndex) step.classList.add("is-current");
        }

        const dot = document.createElement("div");
        dot.className = "track-dot";
        step.appendChild(dot);

        const label = document.createElement("div");
        label.className = "track-label";
        label.textContent = STATUS_LABELS[status];
        step.appendChild(label);

        container.appendChild(step);
    });

    if (isRejected) {
        const rejectedNote = document.createElement("div");
        rejectedNote.className = "track-rejected";
        const chip = document.createElement("span");
        chip.className = "status-badge status-rejected";
        chip.textContent = STATUS_LABELS.rejected;
        rejectedNote.appendChild(chip);
        const hint = document.createElement("span");
        hint.className = "muted";
        hint.textContent = "فرآیند بررسی این درخواست پایان یافته است.";
        rejectedNote.appendChild(hint);
        container.appendChild(rejectedNote);
    }
}

async function fetchTrackingStatus(trackingCode) {
    return apiFetch(`/api/v1/track/${encodeURIComponent(trackingCode)}`);
}

document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("tracking-code");
    const submitButton = document.getElementById("track-submit");
    const errorEl = document.querySelector('[data-error-for="tracking-code"]');
    const resultSection = document.getElementById("result-section");

    if (!submitButton) return;

    const runLookup = async () => {
        if (errorEl) errorEl.textContent = "";
        resultSection.hidden = true;

        const trackingCode = input.value.trim();
        if (!trackingCode) {
            if (errorEl) {
                errorEl.textContent = "وارد کردن کد پیگیری اجباری است.";
                errorEl.focus();
            }
            return;
        }

        const response = await fetchTrackingStatus(trackingCode);

        if (response.status === 429) {
            if (errorEl) {
                errorEl.textContent = "تعداد تلاش‌ها بیش از حد مجاز است؛ کمی بعد دوباره تلاش کنید.";
                errorEl.focus();
            }
            return;
        }
        if (!response.ok) {
            if (errorEl) {
                errorEl.textContent = "کد پیگیری نامعتبر است یا درخواستی با این کد یافت نشد.";
                errorEl.focus();
            }
            return;
        }

        const data = await response.json();
        document.getElementById("result-job").textContent = data.job_position;
        document.getElementById("result-updated").textContent = new Date(data.updated_at).toLocaleString("fa-IR");
        const badge = document.getElementById("result-status-badge");
        badge.className = `status-badge status-${data.status}`;
        badge.textContent = STATUS_LABELS[data.status] || data.status;
        renderSteps(data.status);
        resultSection.hidden = false;
    };

    submitButton.addEventListener("click", runLookup);

    // اگر از دکمهٔ «پیگیری وضعیت درخواست» در صفحهٔ موفقیت ثبت‌نام با ?code=... وارد شده باشد،
    // کد از پیش پر و جست‌وجو خودکار اجرا می‌شود تا کاربر دوباره تایپ نکند.
    const codeFromUrl = new URLSearchParams(window.location.search).get("code");
    if (codeFromUrl) {
        input.value = codeFromUrl;
        runLookup();
    }
});
