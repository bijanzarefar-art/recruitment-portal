// جزئیات پرونده کارمند: خواندن از API با کنترل مجوز سروری؛ دانلود فقط از مسیر امن (T044/T045).
// افزودن یادداشت و تغییر وضعیت (T052) با کنترل نسخه (409) و نمایش امن متن (textContent).
import { apiFetch } from "./csrf.js";

const STATUS_LABELS = {
    new: "در انتظار غربالگری اولیه",
    phone: "تماس اولیه انجام شد",
    interview: "دعوت به مصاحبه",
    approved: "تأیید اولیه",
    rejected: "عدم ادامه فرآیند",
    hired: "استخدام شد",
};

function text(id, value) {
    document.getElementById(id).textContent = value || "—";
}

const REVIEWER_ROLE_LABELS = { recruiter: "کارشناس جذب", hiring_manager: "مدیر استخدام" };

// فهرست کارمندان واجد شرایط دریافت ارجاع (فقط کارشناس جذب/مدیر استخدام فعال — FR-041) را از
// پنل مدیریت کاربران می‌خواند؛ فقط hr_manager به /staff/users دسترسی دارد (همان نقشی که اصلاً
// مجاز به ارجاع است)، پس ۴۰۳ برای نقش‌های دیگر بی‌اثر و قابل‌انتظار است.
async function loadEligibleReviewers() {
    const select = document.getElementById("assign-reviewer-id");
    if (!select) return;
    const response = await apiFetch("/api/v1/staff/users");
    if (!response.ok) return;
    const users = await response.json();
    users
        .filter((u) => u.is_active && (u.role === "recruiter" || u.role === "hiring_manager"))
        .forEach((u) => {
            const option = document.createElement("option");
            option.value = u.id;
            option.textContent = `${u.username} (${REVIEWER_ROLE_LABELS[u.role]})`;
            select.appendChild(option);
        });
}

let currentVersion = null;

async function loadDetail() {
    const id = window.APPLICATION_ID;
    const response = await apiFetch(`/api/v1/staff/applications/${id}`);
    const loadingEl = document.getElementById("loading-state");
    const errorEl = document.getElementById("error-state");

    if (!response.ok) {
        loadingEl.hidden = true;
        errorEl.hidden = false;
        errorEl.textContent = "این پرونده یافت نشد یا شما مجوز مشاهده آن را ندارید.";
        return;
    }

    const data = await response.json();
    loadingEl.hidden = true;
    errorEl.hidden = true;
    document.getElementById("detail-card").hidden = false;
    currentVersion = data.version;

    const statusSelect = document.getElementById("status-select");
    statusSelect.innerHTML = "";
    Object.keys(STATUS_LABELS).forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = STATUS_LABELS[value];
        if (value === data.status) option.selected = true;
        statusSelect.appendChild(option);
    });

    text("applicant-name", `${data.first_name} ${data.last_name}`);
    text("tracking-code", `کد پیگیری: ${data.tracking_code}`);
    const badge = document.getElementById("status-badge");
    badge.textContent = STATUS_LABELS[data.status] || data.status;
    badge.className = `status-badge status-${data.status}`;

    text("d-mobile", data.mobile_snapshot);
    text("d-city", data.city);
    text("d-job", data.job_position);
    text("d-experience", data.experience);
    text("d-availability", data.availability);
    text("d-last-title", data.last_title);
    text("d-last-company", data.last_company);
    text("d-created", new Date(data.created_at).toLocaleString("fa-IR"));

    const previousNotice = document.getElementById("previous-applications-notice");
    if (data.previous_applications && data.previous_applications.length) {
        previousNotice.hidden = false;
        previousNotice.textContent = `این متقاضی ${data.previous_applications.length} درخواست قبلی (در دامنه مجوز شما) دارد.`;
    } else {
        previousNotice.hidden = true;
    }

    const reviewerEl = document.getElementById("reviewer-current");
    if (data.reviewer) {
        const roleLabel = data.reviewer.role === "hiring_manager" ? "مدیر استخدام" : "کارشناس جذب";
        reviewerEl.textContent = `بررسی‌کننده فعلی: ${roleLabel} (شناسه: ${data.reviewer.id})`;
    } else {
        reviewerEl.textContent = "هنوز هیچ ارجاعی ثبت نشده است.";
    }

    const notesList = document.getElementById("notes-list");
    const notesEmpty = document.getElementById("notes-empty");
    notesList.innerHTML = "";
    if (!data.notes.length) {
        notesEmpty.hidden = false;
    } else {
        notesEmpty.hidden = true;
        data.notes.forEach((note) => {
            const div = document.createElement("div");
            div.className = "card";
            div.style.marginBottom = "8px";
            const author = document.createElement("div");
            author.className = "muted";
            author.textContent = `${note.author} — ${new Date(note.created_at).toLocaleString("fa-IR")}`;
            const body = document.createElement("div");
            body.textContent = note.body; // textContent، نه innerHTML (اصل VII).
            div.appendChild(author);
            div.appendChild(body);
            notesList.appendChild(div);
        });
    }
}

function setupActions() {
    const id = window.APPLICATION_ID;

    const downloadLink = document.getElementById("download-link");
    downloadLink.addEventListener("click", async (event) => {
        event.preventDefault();
        const resumeResponse = await apiFetch(`/api/v1/staff/applications/${id}/resume`);
        if (!resumeResponse.ok) {
            document.getElementById("download-error").textContent = "رزومه در حال حاضر قابل دانلود نیست.";
            return;
        }
        const blob = await resumeResponse.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "resume";
        a.click();
        URL.revokeObjectURL(url);
    });

    const noteForm = document.getElementById("note-form");
    noteForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const noteError = document.getElementById("note-error");
        noteError.textContent = "";
        const body = document.getElementById("note-body").value;
        const resp = await apiFetch(`/api/v1/staff/applications/${id}/notes`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ body }),
        });
        if (!resp.ok) {
            noteError.textContent = "ثبت یادداشت ناموفق بود؛ ممکن است دسترسی شما به این پرونده لغو شده باشد.";
            return;
        }
        document.getElementById("note-body").value = "";
        await loadDetail();
    });

    const assignForm = document.getElementById("assign-form");
    const assignError = document.getElementById("assign-error");

    assignForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        assignError.textContent = "";
        const reviewerId = document.getElementById("assign-reviewer-id").value.trim();
        if (!reviewerId) {
            assignError.textContent = "انتخاب کارمند الزامی است.";
            return;
        }
        const resp = await apiFetch(`/api/v1/staff/applications/${id}/assignments`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reviewer_id: reviewerId }),
        });
        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            assignError.textContent = payload.message || "ثبت ارجاع ناموفق بود.";
            return;
        }
        document.getElementById("assign-reviewer-id").value = "";
        await loadDetail();
    });

    document.getElementById("revoke-submit").addEventListener("click", async () => {
        assignError.textContent = "";
        const resp = await apiFetch(`/api/v1/staff/applications/${id}/assignments`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reviewer_id: null }),
        });
        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            assignError.textContent = payload.message || "لغو ارجاع ناموفق بود.";
            return;
        }
        await loadDetail();
    });

    const statusForm = document.getElementById("status-form");
    statusForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const statusError = document.getElementById("status-error");
        const conflictNotice = document.getElementById("status-conflict-notice");
        statusError.textContent = "";
        conflictNotice.hidden = true;

        const to_status = document.getElementById("status-select").value;
        const reason = document.getElementById("status-reason").value;
        const resp = await apiFetch(`/api/v1/staff/applications/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ to_status, reason, expected_version: currentVersion }),
        });

        if (resp.status === 409) {
            conflictNotice.hidden = false;
            return;
        }
        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            statusError.textContent = payload.message || "تغییر وضعیت ناموفق بود.";
            return;
        }
        document.getElementById("status-reason").value = "";
        await loadDetail();
    });

    document.getElementById("status-refresh-button").addEventListener("click", async () => {
        document.getElementById("status-conflict-notice").hidden = true;
        await loadDetail();
    });
}

document.addEventListener("DOMContentLoaded", () => {
    setupActions();
    loadDetail();
    loadEligibleReviewers();
});
