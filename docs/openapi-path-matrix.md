# ماتریس تطبیق ۲۳ مسیر OpenAPI با کد

منبع قرارداد: `specs/001-recruitment-portal/contracts/openapi.yaml`. ستون «آزمون» فایل‌های
واقعی موجود (فراتر از ۶ آزمون قرارداد) را فهرست می‌کند. علامت ⚠️ = پوشش ناقص یا نیازمند تأیید.

| # | Method / Path | احراز هویت (کد) | نقش / دامنه رکوردی | CSRF | ورودی | خروجی | خطاها | صفحه‌بندی | Rate limit | آزمون |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | GET `/jobs` | عمومی (`authentication_classes=[]`, `AllowAny`) | — (فقط `status=open`) | — | — | `JobPositionPublic` ×N | — | خیر (`pagination_class=None`) | — | `test_openapi_code_agreement.py::test_jobs_public_list_*`، `test_us1_smoke` |
| 2 | GET `/privacy-notice` | عمومی | — | — | — | `PrivacyNotice` | — | — | — | ✅ **این دور اضافه شد**: `test_privacy_notice_public` |
| 3 | POST `/auth/candidate/otp/request` | عمومی | — | (بدون نشست) | `mobile`, `purpose` | 202 یکسان | 202 برای عبور از نرخ (FR-016) | — | OTP: ۵/ساعت، ۱۰/روز | `test_candidate_otp.py` |
| 4 | POST `/auth/candidate/otp/verify` | عمومی | — | — | `mobile`,`purpose`,`code` (۶ رقم) | 200 + کوکی | 400، 401 | — | همان بالا | `test_candidate_otp.py` (۷ فایل) |
| 5 | POST `/auth/candidate/logout` | `CandidateSessionAuthentication` | `IsCandidate` | ✅ | — | 204 | 401/403 | — | — | `test_security_hardening.py` |
| 6 | POST `/candidate/uploads` | متقاضی | `IsCandidate` (مالک) | ✅ | multipart `file` | `UploadStatus` | 400، **413**، **415** | — | — | `test_attachment_upload.py`، `test_us1_smoke.py` (۴۱۳/۴۱۵) |
| 7 | GET `/candidate/uploads/{id}` | متقاضی | مالک (`candidate=request.user`) | — | path id | `UploadStatus` | 404 فقط | — | — | `test_attachment_upload.py` |
| 8 | POST `/candidate/applications` | متقاضی | مالک | ✅ | `ApplicationCreateRequest` + `Idempotency-Key` | 201/200 رسید | 400، 409 | — | — | `test_application_submission_concurrency.py`، `test_us1_smoke` |
| 9 | GET `/candidate/applications` | متقاضی | مالک | — | — | `{count,results}` **بدون صفحه‌بندی** | 401/403 | **خیر (عمدی)** | — | `test_candidate_privacy.py` |
| 10 | GET `/candidate/applications/{id}` | متقاضی | مالک | — | path id | `ApplicationPublicDetail` | **404 فقط (هرگز ۴۰۳)** | — | — | `test_candidate_privacy.py` |
| 11 | POST `/auth/staff/login` | عمومی | — | — | `username`,`password` | `mfa_challenge_id` | 401، **429** | — | ✅ FR-047 | `test_staff_login_rate_limit.py` |
| 12 | POST `/auth/staff/mfa/verify` | عمومی | — | — | `mfa_challenge_id`,`code` | 200 + نشست | 401، **429** | — | ✅ FR-047 | `test_staff_login_rate_limit.py` |
| 13 | POST `/auth/staff/logout` | نشست Django | هر کارمند | ✅ | — | 204 | — | — | — | `test_security_hardening.py` |
| 14 | GET `/staff/applications` | نشست Django | `get_applications_queryset` (منع پیش‌فرض) | — | ۶ فیلتر + `page`,`page_size` | `PaginatedStaffApplications` (سبک) | 401/403 | ✅ 25/بیشینه ۱۰۰ | — | `test_staff_access_matrix.py`، `test_openapi_code_agreement.py` |
| 15 | GET `/staff/applications/metrics` | نشست | همان دامنهٔ فهرست | — | `status`,`job_position` | `{total,by_status}` | 401/403 | — | — | `test_staff_access_matrix.py:88` |
| 16 | GET `/staff/applications/{id}` | نشست | دامنه (ارجاع فعال) | — | path id | `ApplicationStaffDetail` | 401/403/404 | — | — | `test_staff_access_matrix.py`، `test_openapi_code_agreement.py` |
| 17 | PATCH `/staff/applications/{id}/status` | نشست | نقش + رکورد + نسخه | ✅ | `to_status`,`expected_version`,`reason` | `ApplicationStaffDetail` | 400، 403، 404، **409** | — | — | `test_status_transitions.py`، `test_application_status_conflict.py` |
| 18 | POST `/staff/applications/{id}/notes` | نشست | رکورد (ارجاع فعال) | ✅ | `body` ۱..۵۰۰۰ | `ApplicationNote` | 401، 404 | — | — | `test_application_notes_and_status_access.py` |
| 19 | PATCH `/staff/applications/{id}/assignments` | نشست | فقط `hr_manager` | ✅ | `reviewer_id` (nullable) | 200 | 403، 404، 409 | — | — | `test_reviewer_assignment.py` |
| 20 | GET `/staff/applications/{id}/resume` | نشست | رکورد + `is_downloadable` | — | path id | octet-stream + `no-store` | 401/403/404 | — | — | `test_resume_download.py` |
| 21 | POST `/staff/exports` | نشست | فقط `hr_manager` | ✅ | `ExportRequest` | CSV/XLSX + `no-store` | 400، 401، 403، **429** | — | ✅ ۵/۱۰دقیقه | `test_staff_export_access.py`، `test_export_rate_limit.py` |
| 22 | GET/POST `/staff/jobs` | نشست | فقط `hr_manager` | ✅ (POST) | `JobPositionWrite` (title) | `JobPositionStaff` ×N / 201 | 401/403 | — | — | `test_job_lifecycle.py` |
| 23 | PATCH `/staff/jobs/{id}` | نشست | فقط `hr_manager` | ✅ | `JobPositionWrite` | `JobPositionStaff` | 400، 401، 403، 404 | — | — | `test_job_lifecycle.py` |
| 24 | PATCH `/staff/jobs/{id}/status` | نشست | فقط `hr_manager` | ✅ | `JobStatusChangeRequest` | `JobPositionStaff` | 400، 401، 403، 404 | — | — | `test_job_lifecycle.py` |

> ۲۵ عملیات روی ۲۳ مسیر وجود دارد (`/candidate/applications` و `/staff/jobs` هر کدام دو متد).

## پوشش آزمون قرارداد

`tests/contract/test_openapi_code_agreement.py` فقط یک **زیرمجموعه** را قفل می‌کند (امنیت صریح،
تطبیق دامنهٔ نشست، نام فیلدهای `UploadStatus`، کلیدهای `previous_applications`/`status_history`،
غیاب فیلدهای جزئیات در فهرست، schema عمومی `/jobs`). بقیهٔ ردیف‌ها توسط آزمون‌های یکپارچه/قرارداد
خارج از آن فایل پوشش داده می‌شوند، همان‌طور که در ستون آخر آمده است.

## شکاف‌هایی که در همین بازبینی یافت و بسته شد

- ردیف ۲ (`/privacy-notice`) هیچ آزمونی نداشت → `test_privacy_notice_is_public_and_matches_schema`.
- ردیف‌های ۲۲–۲۴ (`/staff/jobs*`): آزمون صریح «کارمند غیر-HR با نشست معتبر» وجود نداشت →
  `test_non_hr_staff_with_valid_session_cannot_patch_job`،
  `test_non_hr_staff_cannot_change_job_status_with_valid_session`،
  `test_non_hr_staff_cannot_list_jobs_with_valid_session`.

## یادداشت باقی‌مانده

- ردیف ۳: پاسخ ۴۲۹ برای OTP عمداً هرگز برنمی‌گردد (FR-016 — پاسخ یکسان)؛ رفتار مستقر و آزموده، صریح باقی می‌ماند.
