// داشبورد HR: فهرست، فیلتر، آمار — همه از API واقعی، بدون localStorage/داده دمو (T045).
import { apiFetch } from "./csrf.js";

const STATUS_LABELS = {
    new: "در انتظار غربالگری اولیه",
    phone: "تماس اولیه انجام شد",
    interview: "دعوت به مصاحبه",
    approved: "تأیید اولیه",
    rejected: "عدم ادامه فرآیند",
    hired: "استخدام شد",
};

function buildQuery() {
    const params = new URLSearchParams();
    const q = document.getElementById("search-box").value.trim();
    const status = document.getElementById("status-filter").value;
    if (q) params.set("q", q);
    if (status) params.set("status", status);
    return params.toString();
}

function setState({ loading = false, empty = false, error = "" }) {
    document.getElementById("loading-state").hidden = !loading;
    document.getElementById("empty-state").hidden = !empty;
    const errorEl = document.getElementById("error-state");
    errorEl.hidden = !error;
    errorEl.textContent = error;
    document.getElementById("results-table").hidden = loading || empty || !!error;
}

async function loadMetrics(query) {
    const response = await apiFetch(`/api/v1/staff/applications/metrics?${query}`);
    if (!response.ok) return;
    const data = await response.json();
    const metricsEl = document.getElementById("metrics");
    metricsEl.innerHTML = "";
    const total = document.createElement("div");
    total.className = "card metric";
    total.innerHTML = `<div class="label">کل پرونده‌ها (در دامنه مجوز شما)</div><div class="value">${data.total}</div>`;
    metricsEl.appendChild(total);
    const active = document.createElement("div");
    const activeCount = (data.by_status.new || 0) + (data.by_status.phone || 0) + (data.by_status.interview || 0) + (data.by_status.approved || 0);
    active.className = "card metric";
    active.innerHTML = `<div class="label">در جریان بررسی</div><div class="value">${activeCount}</div>`;
    metricsEl.appendChild(active);
}

async function loadResults() {
    setState({ loading: true });
    const query = buildQuery();
    try {
        const response = await apiFetch(`/api/v1/staff/applications?${query}`);
        if (!response.ok) {
            setState({ error: "بارگذاری فهرست ناموفق بود؛ ممکن است دسترسی لازم را نداشته باشید." });
            return;
        }
        const data = await response.json();
        document.getElementById("result-count").textContent = `${data.count} پرونده`;

        if (!data.results.length) {
            setState({ empty: true });
            return;
        }

        const rows = document.getElementById("result-rows");
        rows.innerHTML = "";
        data.results.forEach((item) => {
            const tr = document.createElement("tr");
            const cells = [
                item.tracking_code,
                `${item.first_name} ${item.last_name}`,
                item.mobile_snapshot,
                item.job_position,
                item.city,
                STATUS_LABELS[item.status] || item.status,
                new Date(item.created_at).toLocaleDateString("fa-IR"),
            ];
            cells.forEach((text) => {
                const td = document.createElement("td");
                td.textContent = text; // بدون innerHTML؛ اعتماد به محتوای سرور ممنوع (اصل VII).
                tr.appendChild(td);
            });
            const actionTd = document.createElement("td");
            const link = document.createElement("a");
            link.href = `/staff/applications/${item.id}`;
            link.className = "link-btn";
            link.textContent = "مشاهده پرونده";
            actionTd.appendChild(link);
            tr.appendChild(actionTd);
            rows.appendChild(tr);
        });
        setState({});
        await loadMetrics(query);
    } catch (err) {
        setState({ error: "خطای ارتباط با سرور." });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadResults();
    document.getElementById("apply-filters").addEventListener("click", loadResults);
    document.getElementById("search-box").addEventListener("keydown", (e) => {
        if (e.key === "Enter") loadResults();
    });
});
