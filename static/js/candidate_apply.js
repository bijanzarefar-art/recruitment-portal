// فرم ثبت درخواست: بارگذاری فایل → ثبت نهایی — بدون هیچ مرحلهٔ OTP (اصل V نسخهٔ ۲.۰.۰).
// بدون IndexedDB/localStorage برای داده شخصی (FR-054)؛ هنگام رد ثبت، داده‌های فرم فقط در
// حافظه همان صفحه (DOM) حفظ می‌شوند، نه در ذخیره‌سازی پایدار مرورگر.
import { apiFetch } from "./csrf.js";

function showFieldError(scope, field, message) {
    const el = scope.querySelector(`[data-error-for="${field}"]`);
    if (el) {
        el.textContent = message || "";
        // فوکوس دسترس‌پذیر روی پنجره خطا تا کاربر صفحه‌خوان فوراً از خطا آگاه شود.
        if (message) el.focus();
    }
}

function clearFieldErrors(form) {
    form.querySelectorAll(".field-error").forEach((el) => (el.textContent = ""));
}

function randomKey() {
    return (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

async function uploadResume(file, uploadAttemptKey) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiFetch("/api/v1/candidate/uploads", {
        method: "POST",
        headers: { "X-Upload-Attempt-Key": uploadAttemptKey },
        body: formData,
    });
    return response.json();
}

async function pollUploadStatus(uploadId, uploadAttemptKey) {
    for (let attempt = 0; attempt < 15; attempt += 1) {
        const response = await apiFetch(`/api/v1/candidate/uploads/${uploadId}`, {
            headers: { "X-Upload-Attempt-Key": uploadAttemptKey },
        });
        const data = await response.json();
        if (data.scan_status === "clean" || data.scan_status === "quarantined" || data.scan_status === "scan_failed" || data.scan_status === "rejected") {
            return data;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw new Error("بررسی فایل بیش از حد انتظار طول کشید.");
}

export function initApplyForm() {
    const form = document.getElementById("apply-form");
    if (!form) return;

    const idempotencyKey = randomKey();
    const uploadAttemptKey = randomKey();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearFieldErrors(form);

        const formData = new FormData(form);
        const fileInput = form.querySelector("#resume");
        const file = fileInput.files[0];
        if (!file) {
            showFieldError(form, "resume", "بارگذاری رزومه اجباری است.");
            return;
        }

        try {
            const upload = await uploadResume(file, uploadAttemptKey);
            const uploadStatus = await pollUploadStatus(upload.id, uploadAttemptKey);
            if (uploadStatus.scan_status !== "clean") {
                showFieldError(form, "resume", "فایل رزومه قابل‌پذیرش نیست؛ لطفاً فایل دیگری بارگذاری کنید.");
                return;
            }

            const response = await apiFetch("/api/v1/candidate/applications", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotencyKey,
                    "X-Upload-Attempt-Key": uploadAttemptKey,
                },
                body: JSON.stringify({
                    first_name: formData.get("first_name"),
                    last_name: formData.get("last_name"),
                    mobile: formData.get("mobile"),
                    email: formData.get("email") || "",
                    city: formData.get("city"),
                    job_position: formData.get("job_position"),
                    employment: formData.get("employment"),
                    experience: formData.get("experience"),
                    availability: formData.get("availability"),
                    last_title: formData.get("last_title") || "",
                    last_company: formData.get("last_company") || "",
                    resume_upload_id: uploadStatus.id,
                    privacy_notice_version: formData.get("privacy_notice_version"),
                    consent: formData.get("consent") === "on",
                }),
            });

            if (response.status === 201 || response.status === 200) {
                const receipt = await response.json();
                document.getElementById("receipt-tracking-code").textContent = receipt.tracking_code;
                document.getElementById("go-to-track-link").href = `/track?code=${encodeURIComponent(receipt.tracking_code)}`;
                const copyButton = document.getElementById("copy-tracking-code");
                copyButton.addEventListener("click", async () => {
                    try {
                        await navigator.clipboard.writeText(receipt.tracking_code);
                        copyButton.textContent = "کپی شد";
                        setTimeout(() => {
                            copyButton.textContent = "کپی کد پیگیری";
                        }, 1500);
                    } catch {
                        // کلیپ‌بورد در دسترس نیست (مثلاً بدون HTTPS)؛ کد همچنان روی صفحه قابل مشاهده است.
                    }
                });
                document.getElementById("apply-success").hidden = false;
                form.closest("#application-section").hidden = true;
            } else {
                const error = await response.json();
                // داده‌های واردشده در همان صفحه (DOM) باقی می‌مانند؛ فرم بازنشانی نمی‌شود (FR-011).
                showFieldError(form, "form", error.message || "ثبت درخواست با خطا مواجه شد.");
            }
        } catch (err) {
            showFieldError(form, "form", "خطای ارتباط با سرور؛ دوباره تلاش کنید.");
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initApplyForm();

    // اگر از صفحهٔ «موقعیت‌های شغلی باز» با ?job=<id> وارد شده باشد، همان موقعیت از پیش انتخاب
    // می‌شود تا دوباره از لیست کشویی جست‌وجو نکند. مقدار فقط وقتی اعمال می‌شود که دقیقاً با یکی
    // از گزینه‌های رندرشدهٔ سروری (موقعیت‌های واقعاً باز) مطابقت داشته باشد.
    const jobSelect = document.getElementById("job_position");
    const jobIdFromUrl = new URLSearchParams(window.location.search).get("job");
    if (jobSelect && jobIdFromUrl && jobSelect.querySelector(`option[value="${CSS.escape(jobIdFromUrl)}"]`)) {
        jobSelect.value = jobIdFromUrl;
    }

    // FR-004: فقط وقتی سابقه کاری «بدون سابقه» نیست، آخرین عنوان شغلی/شرکت اجباری است.
    const experienceSelect = document.getElementById("experience");
    const lastTitle = document.getElementById("last_title");
    const lastCompany = document.getElementById("last_company");
    if (experienceSelect && lastTitle && lastCompany) {
        const syncRequired = () => {
            const required = experienceSelect.value !== "no_experience";
            lastTitle.required = required;
            lastCompany.required = required;
        };
        experienceSelect.addEventListener("change", syncRequired);
        syncRequired();
    }

    const resumeInput = document.getElementById("resume");
    const resumeStatus = document.getElementById("resume-status");
    if (resumeInput && resumeStatus) {
        resumeInput.addEventListener("change", () => {
            const file = resumeInput.files[0];
            resumeStatus.textContent = file ? `فایل انتخاب‌شده: ${file.name}` : "";
        });
    }
});
