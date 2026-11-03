// مدیریت موقعیت شغلی (T061)؛ مجوز واقعی فقط در سرور (`IsHrManager`) بررسی می‌شود.
// چرخه وضعیت (FR-039a): draft → open → closed → open؛ ورود به open = بازگشایی/فعال‌سازی.
import { apiFetch } from "./csrf.js";
import { applyStagger } from "./motion.js";

const STATUS_LABELS = { draft: "پیش‌نویس", open: "باز", closed: "بسته" };

async function loadJobs() {
    const resp = await apiFetch("/api/v1/staff/jobs");
    const loadingEl = document.getElementById("jobs-loading");
    if (!resp.ok) {
        loadingEl.textContent = "فهرست موقعیت‌ها در دسترس نیست (ممکن است مجوز لازم را نداشته باشید).";
        return;
    }
    const jobs = await resp.json();
    loadingEl.hidden = true;
    const table = document.getElementById("jobs-table");
    table.hidden = false;
    const rows = document.getElementById("jobs-rows");
    rows.innerHTML = "";

    jobs.forEach((job) => {
        const tr = document.createElement("tr");

        const titleTd = document.createElement("td");
        titleTd.textContent = job.title;
        if (job.requirements) {
            const reqDiv = document.createElement("div");
            reqDiv.className = "muted";
            reqDiv.style.marginTop = "4px";
            reqDiv.style.fontWeight = "400";
            reqDiv.style.whiteSpace = "pre-line";
            reqDiv.textContent = job.requirements;
            titleTd.appendChild(reqDiv);
        }
        const deptTd = document.createElement("td");
        deptTd.textContent = job.department || "—";
        const locTd = document.createElement("td");
        locTd.textContent = job.location || "—";
        const statusTd = document.createElement("td");
        statusTd.textContent = STATUS_LABELS[job.status] || job.status;

        const actionsTd = document.createElement("td");
        if (job.status === "draft" || job.status === "closed") {
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "btn ghost";
            openBtn.textContent = job.status === "draft" ? "فعال‌سازی" : "بازگشایی";
            openBtn.addEventListener("click", () => changeStatus(job.id, "open"));
            actionsTd.appendChild(openBtn);
        } else if (job.status === "open") {
            const closeBtn = document.createElement("button");
            closeBtn.type = "button";
            closeBtn.className = "btn ghost";
            closeBtn.textContent = "بستن";
            closeBtn.addEventListener("click", () => changeStatus(job.id, "closed"));
            actionsTd.appendChild(closeBtn);
        }

        tr.appendChild(titleTd);
        tr.appendChild(deptTd);
        tr.appendChild(locTd);
        tr.appendChild(statusTd);
        tr.appendChild(actionsTd);
        rows.appendChild(tr);
    });
    applyStagger(rows, "anim-in-row");
}

async function changeStatus(jobId, status) {
    const resp = await apiFetch(`/api/v1/staff/jobs/${jobId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
    });
    if (resp.ok) {
        await loadJobs();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadJobs();

    document.getElementById("create-job-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorEl = document.getElementById("create-job-error");
        errorEl.textContent = "";

        const title = document.getElementById("job-title").value;
        const department = document.getElementById("job-department").value;
        const location = document.getElementById("job-location").value;
        const requirements = document.getElementById("job-requirements").value;

        const resp = await apiFetch("/api/v1/staff/jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, department, location, requirements }),
        });
        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            errorEl.textContent = payload.message || "ایجاد موقعیت ناموفق بود.";
            return;
        }
        document.getElementById("create-job-form").reset();
        await loadJobs();
    });
});
