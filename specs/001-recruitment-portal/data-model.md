# مدل داده فاز ۱: نسخه اولیه پورتال فارسی جذب و استخدام

منبع: موجودیت‌های کلیدی `spec.md`، بخش «مدل‌های اصلی» و «قیود دیتابیس» ورودی کاربر، و تصمیم‌های
`research.md`. همه کلیدها UUID، همه زمان‌ها UTC (`DateTimeField(auto_now_add=...)` و مشابه)، موبایل
و شناسه‌های کاربری/رکوردی رشته‌ای (اصل XII، FR-059).

## StaffUser

کاربر کارمند؛ گسترش `AbstractUser` یا مدل جدا مرتبط با `auth.User`.

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | کلید اصلی |
| `role` | Enum: `recruiter`, `hiring_manager`, `hr_manager`, `system_operator` | نقش کارمند (FR-018) |
| `is_active` | bool | غیرفعال‌سازی فوری دسترسی |
| `totp_confirmed_at` | datetime? | زمان تکمیل enrollment دستگاه `django-otp` |
| `created_by` | FK → StaffUser? | چه کسی حساب را ساخته (برای حسابرسی FR-020) |
| `created_at` | datetime | |

قید: ساخت از طریق فرمان مدیریتی **یا** رابط مدیریت کاربران (پنل ادمین، US7) محدود انجام می‌شود،
نه ثبت‌نام عمومی (FR-020). اپراتور سامانه نقشی مجزا و بدون دسترسی تجاری HR است (FR-021). رابط
مدیریت کاربران از همین مدل و همین enum نقش استفاده می‌کند — مدل یا enum جدیدی لازم نیست؛ فقط
سرویس/API/صفحهٔ تازه در `apps/accounts` اضافه می‌شود (FR-021a تا FR-021d؛ «ادمین» = نقش موجود
`hr_manager`، نه نقش جدید — رجوع به فرضیات spec.md).

## Candidate

متقاضی **هیچ هویت تأییدشده‌ای ندارد** (اصل V نسخهٔ ۲.۰.۰: OTP متقاضی کاملاً حذف شد). یک ردیف
`Candidate` فقط «مجموعهٔ موبایل‌های خوداظهاری» را برای اعمال قاعدهٔ جلوگیری از ثبت تکراری نگه
می‌دارد؛ **صفر معنای احراز هویت** دارد.

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | کلید اصلی |
| `mobile` | `CharField`, یکتا | مقدار نرمال‌شده `09xxxxxxxxx` که متقاضی تایپ کرده — **بدون تأیید مالکیت** |
| `created_at` | datetime | |

`verified_at` و مدل `OTPChallenge` حذف می‌شوند (دیگر هیچ چالشی وجود ندارد).

قید: `mobile` یکتا و رشته‌ای (نه عددی) — این یکتایی فقط برای جلوگیری از ثبت هم‌زمان چندین
درخواست فعال با یک شماره است، نه برای شناسایی هویت واقعی.

## TrackingLookupRateCounter

شمارندهٔ اتمی نرخ‌محدودسازی جست‌وجوی کد پیگیری (FR-043)، جایگزین `OtpRateCounter`.

| فیلد | نوع | توضیح |
|---|---|---|
| `ip_address` | `CharField` | آدرس IP کلاینت |
| `window_start` | datetime | ابتدای پنجرهٔ شمارش |
| `count` | `PositiveIntegerField` | تعداد تلاش‌های پیگیری در این پنجره |

قید: یکتایی `(ip_address, window_start)`؛ افزایش اتمی با `UPDATE ... RETURNING` یا
`select_for_update()`. آستانه تنظیم‌پذیر از تنظیمات (پیشنهادی `TRACKING_LOOKUP_IP_LIMIT=20` در
۱۰ دقیقه — نیازمند تصویب مالک پروژه، مشابه FR-047).

## JobPosition

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `title` | `CharField` | |
| `department` | `CharField` | واحد سازمانی |
| `location` | `CharField` | |
| `status` | Enum: `draft`, `open`, `closed` | چرخه وضعیت صریح (FR-039a)؛ بدون `is_published` جدا |
| `created_at` / `updated_at` | datetime | |

قاعده (FR-039a، تصمیم قطعی): انتقال‌های مجاز فقط `draft→open`، `open→closed`، `closed→open`
(بازگشایی)؛ هر انتقال دیگر (مثلاً `draft→closed` یا بازگشت به `draft`) رد می‌شود. فقط `open`
پذیرای درخواست جدید است؛ `GET /jobs` عمومی فقط `open` را برمی‌گرداند. بستن موقعیت فقط جلوی ثبت
درخواست جدید را می‌گیرد؛ سوابق قبلی همچنان در دامنه مجوز هر کارمند قابل‌مشاهده‌اند (FR-039).
بازگشایی (ورود به `open` از هر مبدأ) فقط با مجوز `hr_manager` و حسابرسی (`job_reopened`) انجام
می‌شود. حذف فیزیکیِ موقعیت ممنوع است (FR-038) — هیچ مسیر DELETE در API وجود ندارد.

## Application

رکورد اصلی هر درخواست؛ نسخه مستقل (snapshot) از اطلاعات فرم، نه ارجاع زنده به پروفایل متقاضی
(FR-056 — ثبت جدید سوابق قبلی را تغییر نمی‌دهد).

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `tracking_code` | `CharField`, یکتا | کد پیگیری تصادفی غیرقابل‌حدس تولیدشده در سرور (FR-007) |
| `candidate` | FK → Candidate | |
| `job_position` | FK → JobPosition | |
| `first_name`, `last_name` | `CharField(1..100)` | trim شده |
| `mobile_snapshot` | `CharField` | کپی موبایل در لحظه ثبت (سوابق قبلی با تغییر بعدی موبایل متقاضی تغییر نمی‌کند) |
| `email` | `CharField(max=254)`, اختیاری | |
| `city` | `CharField(max=100)` | نرمال‌شده برای جست‌وجو |
| `employment` | Enum | `full_time`, `part_time`, `unemployed`, `student`, `other` |
| `experience` | Enum | `no_experience`, `under_1`, `years_1_3`, `years_3_5`, `years_5_10`, `over_10` |
| `availability` | Enum | `immediate`, `within_2_weeks`, `weeks_2_4`, `over_1_month` |
| `last_title`, `last_company` | `CharField(max=200)`, اجباری مگر `no_experience` | |
| `status` | Enum | `new`, `phone`, `interview`, `approved`, `rejected`, `hired` |
| `version` | `IntegerField` | کنترل هم‌زمانی خوش‌بینانه (FR-029) |
| `idempotency_key` | `CharField` | کلید تکرارپذیری درخواست ثبت (ارجاع به `IdempotencyRecord`) |
| `created_at` / `updated_at` | datetime | |

**قیود**:
- یکتایی شرطی `(candidate_id, job_position_id)` فقط وقتی `status` در
  `{new, phone, interview, approved}` است (FR-008) — با `UniqueConstraint(condition=...)` در
  PostgreSQL.
- یکتایی `tracking_code`.
- اعتبارسنجی مقادیر مجاز Enum و طول رشته در serializer/سرویس (نه فقط در دیتابیس).
- ایندکس‌های `(status, created_at, id)`، `(job_position, created_at, id)`، `(reviewer)`،
  `(candidate)` — کلید سوم `id` برای مرتب‌سازی پایدار با زمان‌های برابر (FR-023).

**گردش وضعیت** (پیاده‌سازی در `apps/applications/statemachine.py`، منبع حقیقت یک جدول انتقال):

```text
new        → phone, interview, rejected
phone      → interview, rejected
interview  → approved, rejected
approved   → hired, rejected
```

`hired` و `rejected` نهایی‌اند؛ بازگشایی/اصلاح فقط توسط `hr_manager` با دلیل اجباری و ثبت در
`StatusHistory` با پرچم `is_exception=True` (FR-031). رد (`rejected`) همیشه به یک دلیل داخلی
اجباری در همان رکورد `StatusHistory` نیاز دارد (FR-030)؛ این دلیل هرگز در سریالایزر عمومی متقاضی
قرار نمی‌گیرد.

**ثبت مجدد پس از رد/استخدام**: بدون محدودیت زمانی یا تعداد، به‌شرط بازگشایی مجدد موقعیت (FR-060)؛
هر ثبت یک رکورد `Application` کاملاً مستقل است.

## ApplicationReviewer

ارجاع فعال یک پرونده به یک بررسی‌کننده؛ **حداکثر یک رکورد فعال در هر لحظه برای هر `Application`**.

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `application` | FK → Application (یکتا در میان ارجاع‌های فعال) | |
| `reviewer` | FK → StaffUser (نقش `recruiter` یا `hiring_manager`) | |
| `reviewer_role_at_assignment` | Enum: `recruiter`, `hiring_manager` | عکس‌فوری نقش در لحظه ارجاع |
| `assigned_by` | FK → StaffUser (باید `hr_manager` باشد) | |
| `assigned_at` | datetime | |
| `revoked_at` | datetime? | پر شدن یعنی ارجاع دیگر فعال نیست |

**قواعد (از جلسه رفع ابهام)**:
- در هر لحظه فقط یک ارجاع فعال (`revoked_at IS NULL`) در هر `Application` مجاز است — قید یکتایی
  شرطی `UniqueConstraint(fields=["application"], condition=Q(revoked_at__isnull=True))`.
- اولین ارجاع یک پرونده همیشه باید به یک کارمند با نقش `recruiter` باشد؛ ارجاع مستقیم به
  `hiring_manager` بدون ارجاع قبلی به یک `recruiter` رد می‌شود (سرویس `applications.services`).
- ارجاع بعدی به یک `hiring_manager` باید ارجاع فعال `recruiter` را همزمان (`revoked_at = now()`)
  باطل کند؛ هر دو عملیات در یک تراکنش.
- حذف/لغو ارجاع، دسترسی مشاهده و دانلود بعدی همان کارمند را بلافاصله لغو می‌کند، بدون اثر روی نسخه
  از پیش دانلودشده (FR-041).

## ApplicationNote

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `application` | FK → Application | |
| `author` | FK → StaffUser | |
| `body` | `TextField(1..5000)` | متن ساده (نه HTML) |
| `created_at` | datetime | |

بدون مسیر ویرایش/حذف معمول در رابط کاربری (FR-026).

## StatusHistory

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `application` | FK → Application | |
| `from_status`, `to_status` | Enum | |
| `changed_by` | FK → StaffUser | |
| `internal_reason` | `TextField`, اجباری برای `rejected` و برای هر تغییر استثنایی | هرگز به متقاضی نشان داده نمی‌شود |
| `is_exception` | bool | بازگشایی/اصلاح وضعیت نهایی توسط `hr_manager` |
| `created_at` | datetime | |

هر تغییر وضعیت و درج ردیف تاریخچه در یک تراکنش واحد انجام می‌شود (FR-028).

## PrivacyNotice / Consent

| مدل | فیلد | توضیح |
|---|---|---|
| `PrivacyNotice` | `version` (یکتا)، `body`، `published_at` | متن نسخه‌بندی‌شده حریم خصوصی/اجازه تماس |
| `Consent` | `application` (یک‌به‌یک)، `privacy_notice` (FK)، `accepted_at` (زمان سرور) | پذیرش اجباری در لحظه ثبت (FR-004) |

## Attachment / AttachmentContent

جداسازی فراداده از محتوای باینری طبق اصل I و FR-052.

**Attachment** (فراداده، سبک، در پرس‌وجوهای فهرست/آمار/خروجی قابل‌واکشی):

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `candidate` | FK → Candidate, **nullable** | در لحظهٔ بارگذاری خالی است (بدون هویت تأییدشده)؛ فقط هنگام ثبت نهایی درخواست در `submit_application` پر می‌شود |
| `application` | FK → Application? , nullable، یکتا | اتصال نهایی؛ خالی تا پیش از تثبیت درخواست |
| `upload_attempt_key` | `CharField` | **تنها** مکانیزم محدودکردن استفاده فایل به همان تلاش ارسال (FR-051؛ اصل V نسخهٔ ۲.۰.۰ — دیگر هویت تأییدشده‌ای برای محدودسازی موازی وجود ندارد) |
| `original_filename` | `CharField` | |
| `detected_mime_type` | `CharField` | از روی magic bytes، نه ادعای کلاینت (FR-049) |
| `size_bytes` | `PositiveIntegerField` | محاسبه سروری |
| `sha256` | `CharField(64)` | محاسبه سروری |
| `scan_status` | Enum: `pending`, `quarantined`, `clean`, `rejected`, `scan_failed` | |
| `created_at` | datetime | |

**AttachmentContent** (محتوای باینری، یک‌به‌یک، هرگز در serializer عمومی/پنل مدیریت):

| فیلد | نوع | توضیح |
|---|---|---|
| `attachment` | OneToOne → Attachment، `on_delete=CASCADE` | |
| `data` | `BinaryField` (`bytea`) | قید دیتابیس: `octet_length(data) BETWEEN 1 AND 5242880` |

قواعد:
- حداکثر یک `Attachment` با `application` غیر-null به ازای هر `Application` (یک رزومه در هر
  درخواست در نسخه اولیه).
- محتوای ثبت‌شده تغییرناپذیر است؛ تعویض فایل = بارگذاری/اسکن جدید + اتصال مجدد فراداده، نه
  به‌روزرسانی `data` موجود.
- فراداده، محتوا و ایجاد `BackgroundJob` نوع `scan` در یک تراکنش ساخته می‌شوند.
- فایل در `pending`/`scan_failed`/`rejected` از هیچ مسیر دانلودی قابل دسترس نیست؛ فقط `clean` و
  در دامنه مجوز رکورد قابل دانلود است.
- بارگذاری‌های بدون `application` که بیش از ۲۴ ساعت از ایجادشان گذشته و قفل فعالی ندارند، توسط
  `cleanup_uploads` در یک تراکنش (فراداده + محتوا) حذف می‌شوند؛ ترتیب قفل‌گیری ثبت و پاک‌سازی یکسان
  است تا فایلی که درحال‌اتصال است حذف نشود.

> **حذف‌شده — OTPChallenge و OtpRateCounter** (اصل V نسخهٔ ۲.۰.۰): هیچ چالش OTP یا شمارندهٔ
> ارسال پیامک در سامانه وجود ندارد. جایگزین شمارنده: `TrackingLookupRateCounter` (بالاتر، FR-043).

## IdempotencyRecord

| فیلد | نوع | توضیح |
|---|---|---|
| `candidate` | FK → Candidate | |
| `idempotency_key` | `CharField` | |
| `request_hash` | `CharField` | هش داده نرمال‌شده درخواست |
| `application` | FK → Application | نتیجه نهایی |
| `created_at` | datetime | نگهداری ۲۴ ساعت |

قید یکتایی `(candidate, idempotency_key)`. تکرار همان کلید با محتوای متفاوت → پاسخ ۴۰۹؛ تکرار با
همان محتوا → بازگرداندن همان `application` (FR-009).

## AuditEvent

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `actor` | FK → StaffUser? / `candidate` FK? | یکی از دو، بسته به نوع عملیات |
| `action` | `CharField` | مثل `status_change`, `resume_download`, `export_started`, `role_granted` |
| `object_type`, `object_id` | `CharField`, UUID | |
| `http_request_id` | `CharField` | برای ردیابی لاگ/حسابرسی |
| `metadata` | `JSONField` | فقط فراداده مجاز (فیلترهای نرمال‌شده، نام ستون، تعداد ردیف و مشابه) |
| `created_at` | datetime | |

نقش دیتابیس برنامه فقط حق `INSERT` روی این جدول دارد (بدون `UPDATE`/`DELETE`) تا تغییرپذیری کمتر
شود؛ مقصد حسابرسی مستقل (مثل ارسال موازی به یک سیستم لاگ متمرکز فقط‌افزودنی) به فاز عملیات موکول
می‌شود. هرگز شامل OTP خام، رمز عبور یا محتوای فایل (اصل VIII، FR-055).

## BackgroundJob

| فیلد | نوع | توضیح |
|---|---|---|
| `id` | UUID | |
| `job_type` | Enum: `scan_attachment`, `cleanup_upload` | |
| `payload` | `JSONField` | فقط شناسه‌ها (مثل `attachment_id`)، هرگز محتوای شخصی فایل |
| `status` | Enum: `pending`, `in_progress`, `succeeded`, `failed` | |
| `lock_expires_at` | datetime? | برای `SELECT ... FOR UPDATE SKIP LOCKED` با مهلت |
| `attempts` | `PositiveSmallIntegerField` | |
| `next_attempt_at` | datetime | تأخیر افزایشی (exponential backoff) |
| `error_code` | `CharField`, اختیاری | |
| `created_at` / `updated_at` | datetime | |

## روابط کلیدی (خلاصه)

```text
Candidate 1---* Application *---1 JobPosition
Application 1---0..1 ApplicationReviewer(active) *---1 StaffUser
Application 1---* ApplicationNote *---1 StaffUser
Application 1---* StatusHistory
Application 1---1 Consent ---* PrivacyNotice
Application 0..1---0..1 Attachment 1---1 AttachmentContent
Candidate 1---* Attachment (قبل از اتصال به یک Application)
```
