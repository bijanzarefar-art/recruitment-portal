// فهرست عمومی موقعیت‌های شغلی باز (بدون ورود) — فقط از GET /api/v1/jobs خوانده می‌شود
// (PublicJobListView، AllowAny)؛ همیشه فقط وضعیت open را برمی‌گرداند (FR-001, FR-002).
import { apiFetch } from "./csrf.js";

document.addEventListener("DOMContentLoaded", async () => {
    const loadingEl = document.getElementById("jobs-loading");
    const emptyEl = document.getElementById("jobs-empty");
    const errorEl = document.getElementById("jobs-error");
    const listEl = document.getElementById("jobs-list");

    const response = await apiFetch("/api/v1/jobs");
    loadingEl.hidden = true;

    if (!response.ok) {
        errorEl.hidden = false;
        return;
    }

    const jobs = await response.json();
    if (!jobs.length) {
        emptyEl.hidden = false;
        return;
    }

    jobs.forEach((job) => {
        const card = document.createElement("section");
        card.className = "card";

        const title = document.createElement("h3");
        title.style.marginTop = "0";
        title.style.paddingTop = "0";
        title.style.borderTop = "none";
        title.textContent = job.title;
        card.appendChild(title);

        if (job.department) {
            const dept = document.createElement("div");
            dept.className = "muted";
            dept.textContent = `واحد: ${job.department}`;
            card.appendChild(dept);
        }
        if (job.location) {
            const loc = document.createElement("div");
            loc.className = "muted";
            loc.style.marginTop = "4px";
            loc.textContent = `محل: ${job.location}`;
            card.appendChild(loc);
        }

        const requirementLines = (job.requirements || "").split("\n").map((line) => line.trim()).filter(Boolean);
        if (requirementLines.length) {
            const reqTitle = document.createElement("div");
            reqTitle.style.marginTop = "14px";
            reqTitle.style.fontWeight = "700";
            reqTitle.style.fontSize = "13px";
            reqTitle.textContent = "شایستگی‌های احراز شغل";
            card.appendChild(reqTitle);

            const reqList = document.createElement("ul");
            reqList.style.margin = "8px 0 0";
            reqList.style.paddingInlineStart = "20px";
            reqList.style.color = "var(--ink-soft)";
            reqList.style.fontSize = "13.5px";
            reqList.style.lineHeight = "1.9";
            requirementLines.forEach((line) => {
                const item = document.createElement("li");
                item.textContent = line;
                reqList.appendChild(item);
            });
            card.appendChild(reqList);
        }

        // فاصلهٔ بالا از CSS (`.grid--equal-cards > .card > .actions-row`) می‌آید تا با
        // `margin-top:auto` جابه‌جا نشود.
        const actions = document.createElement("div");
        actions.className = "actions-row";
        const applyLink = document.createElement("a");
        applyLink.className = "btn primary";
        applyLink.href = `/apply?job=${encodeURIComponent(job.id)}`;
        applyLink.textContent = "ثبت درخواست برای این موقعیت";
        actions.appendChild(applyLink);
        card.appendChild(actions);

        listEl.appendChild(card);
    });
});
