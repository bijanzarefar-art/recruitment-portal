#!/usr/bin/env bash
# قالب پشتیبان‌گیری PostgreSQL (T067/T067b) — **آماده‌سازی، نه اجرای واقعی**.
#
# این اسکریپت هیچ چیزی را در این محیط اجرا نمی‌کند؛ فقط مسیر و رویه را می‌سازد تا وقتی مقصد
# پشتیبان مستقل (O6) و پنجرهٔ عملیاتی مشخص شد، با تنظیم متغیرهای محیطی اجرا شود.
#
# استفاده:
#   export PGHOST=... PGPORT=5432 PGDATABASE=... PGUSER=... PGPASSWORD=...
#   export BACKUP_DIR=/mnt/independent-backup/reqruitment   # مقصد خارج از میزبان برنامه
#   ./scripts/backup.sh
#
# الزامات ایمنی (اصل X):
#   - BACKUP_DIR باید خارج از میزبان برنامه باشد؛ اسکریپت این را بررسی می‌کند.
#   - نام فایل شامل تاریخ UTC است.
#   - اسکریپت بعد از پایان، حجم و sha256 را چاپ می‌کند تا صحت قابل‌بررسی باشد.
set -euo pipefail

: "${PGDATABASE:?PGDATABASE تنظیم نشده}"
: "${BACKUP_DIR:?BACKUP_DIR تنظیم نشده (مقصد پشتیبان مستقل)}"

APP_HOST_ROOT="${APP_HOST_ROOT:-}"

if [[ -n "$APP_HOST_ROOT" && "$BACKUP_DIR" == "$APP_HOST_ROOT"* ]]; then
  echo "خطا: BACKUP_DIR داخل میزبان برنامه است؛ مقصد مستقل لازم است (O6)." >&2
  exit 1
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "خطا: مقصد پشتیبان وجود ندارد: $BACKUP_DIR" >&2
  echo "ابتدا مقصد مستقل (سرور پشتیبان/دیسک جدا) را بسازید و دوباره اجرا کنید." >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTFILE="$BACKUP_DIR/${PGDATABASE}_${STAMP}.dump"

echo "در حال تهیه پشتیبان: $OUTFILE"
pg_dump --format=custom --compress=9 --file="$OUTFILE"

# رمزگذاری (اختیاری اما توصیه‌شده) — اگر رمز تنظیم شده باشد.
if [[ -n "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ]]; then
  echo "رمزگذاری پشتیبان..."
  gpg --batch --yes --symmetric --cipher-algo AES256 \
      --passphrase "$BACKUP_ENCRYPTION_PASSPHRASE" "$OUTFILE"
  rm -f "$OUTFILE"
  OUTFILE="${OUTFILE}.gpg"
fi

SIZE="$(du -h "$OUTFILE" | cut -f1)"
SHA="$(sha256sum "$OUTFILE" | cut -d' ' -f1)"

echo "پشتیبان ساخته شد:"
echo "  مسیر: $OUTFILE"
echo "  حجم:  $SIZE"
echo "  sha256: $SHA"
echo
echo "برای آزمون بازیابی، این فایل را در محیط جدا با pg_restore بازیابی و sha256 محتوای رزومه‌ها را مقایسه کنید."
