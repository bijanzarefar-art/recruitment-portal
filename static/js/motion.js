// ورود پلکانی ردیف‌ها/کارت‌های تازه‌رندرشده (جدول‌ها، فهرست‌ها، تابلوها). صرفاً یک کلاس CSS
// و تأخیر فزاینده اضافه می‌کند؛ هیچ منطق تجاری اینجا نیست. حرکت واقعی در static/css/base.css
// تعریف شده و زیر prefers-reduced-motion خاموش می‌شود — این فایل فقط هماهنگ‌کنندهٔ تأخیرهاست.
const MAX_STAGGER_ITEMS = 10;
const STEP_MS = 35;

export function applyStagger(container, animClass = "anim-in") {
    if (!container) return;
    Array.from(container.children).forEach((el, index) => {
        el.classList.add(animClass);
        el.style.animationDelay = `${Math.min(index, MAX_STAGGER_ITEMS) * STEP_MS}ms`;
    });
}
