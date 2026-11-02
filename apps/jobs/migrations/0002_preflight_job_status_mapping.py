"""
گام ۱ از ۲ برای مهاجرت چرخه وضعیت JobPosition (FR-039a). این مهاجرت **هیچ داده‌ای را تغییر
نمی‌دهد**؛ فقط بررسی می‌کند که آیا تمام ردیف‌های موجود قابل نگاشت به اسکیمای جدید با یک تصمیم
مصوب هستند یا خیر، و در صورت نبود چنین تصمیمی، اجرای مهاجرت را متوقف می‌کند.

نگاشت مصوب (فقط موارد تأییدشدهٔ کاربر):

| is_published | status قدیمی | status جدید |
|---|---|---|
| True  | open   | open   |
| True  | closed | closed |

بی‌نگاشت (باعث توقف امن — نه حدس، نه حذف، نه تغییر):
- `is_published=False` (هر وضعیتی، از جمله `closed`) — تصمیم نگاشت به `draft` **مصوب نیست**.
- `status='archived'` (با هر مقدار `is_published`).
- هر مقدار ناشناخته در `status`.

مشکل واقعی این است که `is_published` در اسکیمای قدیمی **دو بُعد را هم‌زمان** کدگذاری می‌کند
(بازبودن + عمومی‌بودن)؛ وضعیت جدید فقط یک بُعد دارد. بنابراین ترکیب‌هایی مثل
`(True, closed)` و `(False, closed)` به‌معنای متفاوت‌ی در اسکیمای قدیمی ولی یک مقدار یکسان در
اسکیمای جدید (`closed` و `draft` اگر مصوب بود) تبدیل می‌شوند و اطلاعات بازگشت‌ناپذیر از دست
می‌رود — به همین دلیل بررسی لازم است، نه صرفاً یک راحتی.

## عملیات امن
- این مهاجرت کاملاً فقط‌خواندنی است؛ هیچ ردیفی UPDATE/DELETE نمی‌شود. اگر بررسی شکست بخورد،
  دلیل ساده است: **هیچ تغییری واقع نشده که نیاز به جبران باشد**.
- برای جلوگیری از نوشتن هم‌زمان روی `JobPosition` هنگام اجرای این مهاجرت و مهاجرت بعدی
  (`0003_job_status_graph`)، این مهاجرت یک قفل `ACCESS EXCLUSIVE` روی جدول می‌گیرد (با
  `LOCK TABLE` درون یک تراکنش). `atomic=True` به‌تنهایی فقط تراکنشی‌بودن همین مهاجرت را تضمین
  می‌کند، نه جلوگیری از نوشتن نویسندگان دیگر؛ قفل جدول این کار را می‌کند. **نکته عملیاتی**:
  در محیط‌هایی که `hot_standby_feedback` یا تراکنش‌های طولانی دیگری وجود دارد، این ممکن است
  تا پایان تراکنش‌های باز مسدود بماند؛ در چنین محیطی اولین خط دفاع همان «توقف سرویس‌های
  نویسنده پیش از اجرای مهاجرت» در راهنمای عملیات است.
"""
from django.db import migrations

# تنها نگاشت‌های تصویب‌شده. کلید: (is_published, status_old) -> مقدار: status_new
APPROVED_MAPPING = {
    (True, "open"): "open",
    (True, "closed"): "closed",
}

# هر ترکیب دیگری (به‌طور صریح یا از طریق مقدار ناشناخته) بی‌نگاشت است.
UNMAPPED_HINT = (
    "راهنمای اقدام:\n"
    "  - این جدول فقط‌خواندنی است؛ هیچ چیزی تغییر نکرده و نیازی به جبران نیست.\n"
    "  - برای هر ردیف، مدیر HR / مدیر داده باید صریحاً بگوید این ردیف در اسکیمای جدید چه "
    "وضعیتی دارد (open یا closed). هیچ نگاشت خودکاری انجام نمی‌شود.\n"
    "  - سپس با یک فرمان مدیریتی جداگانه و ثبت‌شده، مقدار `is_published` و `status` همان ردیف را "
    "طبق همان تصمیم اصلاح کنید (مثلاً `is_published=True` و `status='open'`)، و این مهاجرت را "
    "دوباره اجرا کنید.\n"
    "  - در اسکیمای قدیمی به‌طور مستقیم مقدار 'draft' ننویسید: آن مقدار در اسکیمای قدیمی "
    "وجود ندارد و `is_published` هنوز معنای مستقل «عمومی» را حمل می‌کند."
)


def _format_unmappable(rows):
    return "\n".join(
        f"  - id={row['id']} title={row['title']!r} is_published={row['is_published']} status={row['status']!r}"
        for row in rows
    )


def preflight(apps, schema_editor):
    # ORM بر روی همان اتصال/alias مهاجرت، تا در هر محیطی (از جمله multi-db) درست کار کند.
    alias = schema_editor.connection.alias
    JobPosition = apps.get_model("jobs", "JobPosition")

    # جلوگیری از نوشتن هم‌زمان روی جدول در طول این مهاجرت و مهاجرت بعدی (`atomic=True` به‌تنهایی
    # فقط تراکنشی‌بودن خودِ مهاجرت را تضمین می‌کند، نه جلوگیری از نویسندگان دیگر).
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('LOCK TABLE "jobs_jobposition" IN ACCESS EXCLUSIVE MODE')

    rows = list(JobPosition.objects.using(alias).all().values("id", "title", "is_published", "status"))
    unmappable = [row for row in rows if (row["is_published"], row["status"]) not in APPROVED_MAPPING]
    if unmappable:
        raise RuntimeError(
            "مهاجرت متوقف شد: ردیف‌های زیر هیچ نگاشت مصوب ندارند (is_published=False، "
            "status='archived'، یا مقدار ناشناخته). هیچ داده‌ای تغییر یا حذف نشد.\n"
            f"{_format_unmappable(unmappable)}\n"
            f"{UNMAPPED_HINT}"
        )


class Migration(migrations.Migration):
    # اجرای هر دو مهاجرت (این گام و گام بعد) در یک تراکنش واحد تا شکست نیمه‌کاره ممکن نباشد.
    # (LOCK TABLE فقط درون تراکنش Atomic معتبر است و کل زمان تراکنش را پوشش می‌دهد.)
    atomic = True

    dependencies = [
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(preflight, migrations.RunPython.noop),
    ]
