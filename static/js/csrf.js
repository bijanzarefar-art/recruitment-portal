// خواندن توکن CSRF از کوکی برای فراخوانی‌های fetch (جایگزین امن ذخیره‌سازی ناامن مرورگر — FR-048).
export function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
}

export async function apiFetch(url, options = {}) {
    const headers = Object.assign({}, options.headers);
    if (options.method && options.method !== "GET") {
        headers["X-CSRFToken"] = getCsrfToken();
    }
    return fetch(url, Object.assign({}, options, { headers, credentials: "same-origin" }));
}
