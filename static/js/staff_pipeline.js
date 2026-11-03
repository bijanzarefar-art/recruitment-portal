// صفحهٔ «فرآیند جذب»: همان GET /api/v1/staff/applications که داشبورد می‌خواند، فقط این‌بار
// همهٔ صفحات را جمع می‌کند و بر اساس status دسته‌بندی می‌کند (نه یک جدول تخت). دامنهٔ مجوز
// دقیقاً همان apps.applications.services.get_applications_queryset سمت سرور است — این صفحه
// هیچ فیلتر/کنترل دسترسی اضافه‌ای روی داده اعمال نمی‌کند.
import { apiFetch } from "./csrf.js";
import { applyStagger } from "./motion.js";

const COLUMNS = [
    { status: "new", label: "در انتظار غربالگری اولیه", badgeClass: "status-new" },
    { status: "phone", label: "تماس اولیه انجام شد", badgeClass: "status-phone" },
    { status: "interview", label: "دعوت به مصاحبه", badgeClass: "status-interview" },
    { status: "approved", label: "تأیید اولیه", badgeClass: "status-approved" },
    { status: "hired", label: "استخدام شد", badgeClass: "status-hired" },
    { status: "rejected", label: "عدم ادامه فرآیند", badgeClass: "status-rejected" },
];

async function fetchAllApplications() {
    const results = [];
    let url = "/api/v1/staff/applications?page_size=100";
    while (url) {
        const response = await apiFetch(url);
        if (!response.ok) throw new Error("fetch failed");
        const data = await response.json();
        results.push(...data.results);
        url = data.next;
    }
    return results;
}

function buildCard(item) {
    const card = document.createElement("a");
    card.className = "pipeline-card";
    card.href = `/staff/applications/${item.id}`;

    const name = document.createElement("div");
    name.className = "pipeline-card-name";
    name.textContent = `${item.first_name} ${item.last_name}`;
    card.appendChild(name);

    const job = document.createElement("div");
    job.className = "pipeline-card-job";
    job.textContent = item.job_position;
    card.appendChild(job);

    const meta = document.createElement("div");
    meta.className = "pipeline-card-meta";
    meta.textContent = `${item.city} · ${new Date(item.created_at).toLocaleDateString("fa-IR")}`;
    card.appendChild(meta);

    return card;
}

async function loadBoard() {
    const loadingEl = document.getElementById("pipeline-loading");
    const errorEl = document.getElementById("pipeline-error");
    const boardEl = document.getElementById("pipeline-board");

    try {
        const applications = await fetchAllApplications();
        loadingEl.hidden = true;
        boardEl.hidden = false;
        boardEl.innerHTML = "";

        COLUMNS.forEach((col) => {
            const items = applications.filter((a) => a.status === col.status);

            const column = document.createElement("section");
            column.className = "pipeline-column";

            const header = document.createElement("div");
            header.className = "pipeline-column-header";
            const badge = document.createElement("span");
            badge.className = `status-badge ${col.badgeClass}`;
            badge.textContent = col.label;
            const count = document.createElement("span");
            count.className = "pipeline-column-count";
            count.textContent = items.length;
            header.appendChild(badge);
            header.appendChild(count);
            column.appendChild(header);

            const list = document.createElement("div");
            list.className = "pipeline-column-list";
            if (!items.length) {
                const empty = document.createElement("div");
                empty.className = "pipeline-empty muted";
                empty.textContent = "پرونده‌ای در این مرحله نیست.";
                list.appendChild(empty);
            } else {
                items.forEach((item) => list.appendChild(buildCard(item)));
                applyStagger(list);
            }
            column.appendChild(list);

            boardEl.appendChild(column);
        });
        applyStagger(boardEl, "anim-in-row");
    } catch (err) {
        loadingEl.hidden = true;
        errorEl.hidden = false;
        errorEl.textContent = "بارگذاری فرآیند جذب ناموفق بود؛ ممکن است دسترسی لازم را نداشته باشید.";
    }
}

document.addEventListener("DOMContentLoaded", loadBoard);
