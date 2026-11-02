"""
گام ۲ از ۲ برای مهاجرت چرخه وضعیت JobPosition (FR-039a): حذف `is_published`، تنظیم `choices`
جدید برای `status` و ایندکس تازه. پیش‌شرط: `0002_preflight_job_status_mapping` با موفقیت اجرا
شده و ثابت کرده هیچ ردیف بی‌نگاشتی وجود ندارد.

## سیاست برگشت — برگشت **غیرقابل‌اجرا** (fail-fast قبل از هر تغییر)
این مهاجرت برگشت‌پذیر نیست: `is_published` ستونی را حذف می‌کند که دو ترکیب مختلف قدیمی
(`(True, closed)` و `(False, closed)`) در وضعیت جدید **یکسان** مستقر می‌شوند. Django هنگام برگشت
نمی‌تواند بداند هر ردیف اصلی‌اش کدام ترکیب بوده؛ درج مقدار پیش‌فرض `False` یک **بازسازی حدسی**
است که ممنوع است.

`RunPython.noop` قبلاً این را بی‌صدا «موفق» نشان می‌داد و برگشت را به عملیات Django روی
`RemoveField` واگذار می‌کرد — یعنی `migrate jobs 0002` ستون را با مقدار اشتباه برمی‌گرداند و
هیچ خطایی نمی‌داد. اکنون ترتیب عملیات برعکس شده:

١. **اول** یک `RunPython` با `reverse_code` که در جهت برگشت `RuntimeError` می‌دهد — **پیش از**
   بازگرداندن `is_published` و پیش از هر تغییر، برگشت با پیام روشن متوقف می‌شود.
۲. عملیات‌های Django در ادامه.
   (در جهت forward، operation اول no-op است؛ هیچ داده‌ای تغییر نمی‌دهد.)

اگر بازیابی از پشتیبان مسیر رسمی است، همان پیام خطای برگشت آن را می‌گوید؛ این مانع **در خودِ
زنجیره عملیات، قبل از هر تغییر** قرار دارد، نه فقط در preflight قبلی.

راهنمای بازیابی واقعی:
  ۱. پیش از اعمال این مهاجرت، از `jobs_jobposition` (یا کل پایگاه‌داده) پشتیبان بگیرید.
  ۲. برای بازگشت، پایگاه‌داده را از همان پشتیبان بازیابی کنید — نه با `migrate jobs 0002`.
  ۳. هرگز `--fake` یا حذف دستی از `django_migrations` بدون backup معتبر مجاز نیست.
"""
from django.db import migrations, models


REVERSE_BLOCKED_MESSAGE = (
    "برگشت به 0002_preflight_job_status_mapping عمداً مسدود است: ستون is_published حذف شده و "
    "بازسازی مقدار اصلی آن غیرممکن است. برای بازگشت، پایگاه‌داده را از پشتیبان گرفته‌شده پیش از "
    "اعمال این مهاجرت بازیابی کنید. --fake یا حذف دستی از django_migrations مجاز نیست."
)


def _blocked_reverse(apps, schema_editor):
    raise RuntimeError(REVERSE_BLOCKED_MESSAGE)


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("jobs", "0002_preflight_job_status_mapping"),
    ]

    operations = [
        # اولین عملیات: در جهت برگشت، پیش از هر تغییر اسکیما/داده، توقف می‌کند.
        migrations.RunPython(migrations.RunPython.noop, _blocked_reverse),
        migrations.RemoveIndex(
            model_name="jobposition",
            name="jobs_jobpos_is_publ_3b6e6c_idx",
        ),
        migrations.RemoveField(
            model_name="jobposition",
            name="is_published",
        ),
        migrations.AlterField(
            model_name="jobposition",
            name="status",
            field=models.CharField(
                choices=[("draft", "پیش‌نویس"), ("open", "باز"), ("closed", "بسته")],
                default="draft",
                max_length=10,
            ),
        ),
        migrations.AddIndex(
            model_name="jobposition",
            index=models.Index(fields=["status"], name="jobs_jobpos_status_8985dd_idx"),
        ),
    ]
