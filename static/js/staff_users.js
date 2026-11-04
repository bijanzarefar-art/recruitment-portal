// مدیریت کاربران از پنل ادمین (US7)؛ مجوز واقعی فقط در سرور (`IsHrManager`) بررسی می‌شود.
import { apiFetch } from "./csrf.js";
import { applyStagger } from "./motion.js";

const ROLE_LABELS = {
    recruiter: "کارشناس جذب",
    hiring_manager: "مدیر استخدام",
    hr_manager: "مدیر HR",
    system_operator: "اپراتور سامانه",
};

async function loadUsers() {
    const resp = await apiFetch("/api/v1/staff/users");
    const loadingEl = document.getElementById("users-loading");
    if (!resp.ok) {
        loadingEl.textContent = "فهرست کارمندان در دسترس نیست (ممکن است مجوز لازم را نداشته باشید).";
        return;
    }
    const users = await resp.json();
    loadingEl.hidden = true;
    const table = document.getElementById("users-table");
    table.hidden = false;
    const rows = document.getElementById("users-rows");
    rows.innerHTML = "";

    users.forEach((user) => {
        const tr = document.createElement("tr");

        // نام کاربری همراه با چیپ وضعیت در همان سلول — تا ستون «وضعیت» جدا لازم نباشد.
        const userTd = document.createElement("td");
        const nameRow = document.createElement("div");
        nameRow.className = "user-cell";
        const nameSpan = document.createElement("span");
        nameSpan.className = "user-cell-name";
        nameSpan.textContent = user.username;
        const statusChip = document.createElement("span");
        statusChip.className = `badge-pill ${user.is_active ? "badge-pill--on" : "badge-pill--off"}`;
        statusChip.textContent = user.is_active ? "فعال" : "غیرفعال";
        nameRow.appendChild(nameSpan);
        nameRow.appendChild(statusChip);
        userTd.appendChild(nameRow);
        tr.appendChild(userTd);

        // نقش همیشه در جدول نمایش داده می‌شود، ولی ویرایشش فقط با کلیک روی «تغییر نقش»
        // باز می‌شود — به‌جای یک select همیشه‌روشن که ارتفاع هر ردیف را دو برابر می‌کرد.
        const roleTd = document.createElement("td");
        roleTd.textContent = ROLE_LABELS[user.role] || user.role;
        tr.appendChild(roleTd);

        const actionsTd = document.createElement("td");
        actionsTd.className = "actions-cell";

        const roleBtn = document.createElement("button");
        roleBtn.type = "button";
        roleBtn.className = "btn ghost btn-sm";
        roleBtn.textContent = "تغییر نقش";
        roleBtn.addEventListener("click", () => {
            const roleSelect = document.createElement("select");
            roleSelect.className = "input input-inline";
            ["recruiter", "hiring_manager", "hr_manager"].forEach((role) => {
                const option = document.createElement("option");
                option.value = role;
                option.textContent = ROLE_LABELS[role];
                if (role === user.role) option.selected = true;
                roleSelect.appendChild(option);
            });
            roleSelect.addEventListener("change", () => updateUser(user.id, { role: roleSelect.value }));
            roleBtn.replaceWith(roleSelect);
            roleSelect.focus();
        });
        actionsTd.appendChild(roleBtn);

        // بازنشانی رمز — برای حسابی که صاحبش رمز را فراموش کرده. با کلیک روی دکمه، یک
        // فیلد رمز همان‌جا باز می‌شود؛ رمز تازه هرگز در فهرست نمایش داده نمی‌شود.
        const passBtn = document.createElement("button");
        passBtn.type = "button";
        passBtn.className = "btn ghost btn-sm";
        passBtn.textContent = "تغییر رمز";
        passBtn.addEventListener("click", () => openPasswordReset(actionsTd, passBtn, user));
        actionsTd.appendChild(passBtn);

        const toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = `btn btn-sm ${user.is_active ? "ghost" : "primary"}`;
        toggleBtn.textContent = user.is_active ? "غیرفعال" : "فعال";
        toggleBtn.addEventListener("click", () => updateUser(user.id, { is_active: !user.is_active }));
        actionsTd.appendChild(toggleBtn);

        // حذف دائمی — جدا از «غیرفعال» که فقط ورود را مسدود می‌کند. تأیید دوباره دارد چون
        // برگشت‌ناپذیر است؛ اگر حساب به سوابق دیگری وابسته باشد سرور ۴۰۹ برمی‌گرداند و پیام
        // همان خطا (نه یک پیام عمومی) نشان داده می‌شود.
        const deleteBtn = document.createElement("button");
        deleteBtn.type = "button";
        deleteBtn.className = "btn danger btn-sm";
        deleteBtn.textContent = "حذف";
        deleteBtn.addEventListener("click", () => deleteUser(user));
        actionsTd.appendChild(deleteBtn);

        tr.appendChild(actionsTd);
        rows.appendChild(tr);
    });
    applyStagger(rows, "anim-in-row");
}

function openPasswordReset(actionsTd, passBtn, user) {
    const input = document.createElement("input");
    input.type = "password";
    input.className = "input input-inline";
    input.placeholder = "رمز جدید";
    input.autocomplete = "new-password";
    input.minLength = 8;

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn primary btn-sm";
    saveBtn.textContent = "ذخیره";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "btn ghost btn-sm";
    cancelBtn.textContent = "انصراف";

    const restore = () => {
        input.remove();
        saveBtn.remove();
        cancelBtn.remove();
        passBtn.hidden = false;
    };

    cancelBtn.addEventListener("click", restore);

    const msg = document.createElement("span");
    msg.className = "inline-msg";

    saveBtn.addEventListener("click", async () => {
        msg.textContent = "";
        msg.classList.remove("inline-msg--error");
        if (input.value.length < 8) {
            msg.textContent = "رمز جدید باید حداقل ۸ کاراکتر باشد.";
            msg.classList.add("inline-msg--error");
            return;
        }
        saveBtn.disabled = true;
        const resp = await apiFetch(`/api/v1/staff/users/${user.id}/password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_password: input.value }),
        });
        saveBtn.disabled = false;
        const body = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            msg.textContent = body.message || "تغییر رمز ناموفق بود.";
            msg.classList.add("inline-msg--error");
            return;
        }
        restore();
        flashNotice(body.message || "رمز عبور بازنشانی شد.");
    });

    passBtn.hidden = true;
    actionsTd.insertBefore(input, passBtn);
    actionsTd.insertBefore(saveBtn, passBtn);
    actionsTd.insertBefore(cancelBtn, passBtn);
    actionsTd.insertBefore(msg, passBtn);
    input.focus();
}

// پیام موفقیت کوتاه بالای جدول — بدون alert (که در برخی محیط‌ها مسدود و همیشه ناخوشایند است).
function flashNotice(text) {
    const el = document.getElementById("users-flash");
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
    clearTimeout(flashNotice._t);
    flashNotice._t = setTimeout(() => {
        el.hidden = true;
    }, 4000);
}

async function deleteUser(user) {
    const confirmed = window.confirm(
        `حذف حساب «${user.username}» برگشت‌ناپذیر است. آیا مطمئن هستید؟`
    );
    if (!confirmed) return;

    const resp = await apiFetch(`/api/v1/staff/users/${user.id}`, { method: "DELETE" });
    if (resp.ok) {
        flashNotice(`حساب «${user.username}» حذف شد.`);
        await loadUsers();
        return;
    }
    const body = await resp.json().catch(() => ({}));
    window.alert(body.message || "حذف ناموفق بود.");
}

async function updateUser(userId, payload) {
    const resp = await apiFetch(`/api/v1/staff/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (resp.ok) {
        await loadUsers();
    } else {
        const body = await resp.json().catch(() => ({}));
        window.alert(body.message || "به‌روزرسانی ناموفق بود.");
        await loadUsers();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadUsers();

    document.getElementById("create-user-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorEl = document.getElementById("create-user-error");
        const resultEl = document.getElementById("create-user-result");
        errorEl.textContent = "";
        resultEl.hidden = true;

        const username = document.getElementById("user-username").value;
        const password = document.getElementById("user-password").value;
        const role = document.getElementById("user-role").value;

        const resp = await apiFetch("/api/v1/staff/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password, role }),
        });
        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            errorEl.textContent = payload.message || "ساخت حساب ناموفق بود.";
            return;
        }
        const data = await resp.json();
        resultEl.textContent = `حساب «${data.username}» ساخته شد و بلافاصله با همین نام‌کاربری/رمز عبور قابل ورود است.`;
        resultEl.hidden = false;
        document.getElementById("create-user-form").reset();
        await loadUsers();
    });
});
