#!/usr/bin/env bash
# قالب چرخش پشتیبان ۱۲ماهه (FR-062، T067b) — **آماده‌سازی، نه اجرای واقعی**.
#
# سیاست مصوب (FR-062): نسخه‌های پشتیبان قدیمی‌تر از ۱۲ ماه خودکار منقضی می‌شوند؛ حذف یک
# رکورد از داده زنده **نباید** مستلزم حذف گذشته‌نگر آن رکورد از پشتیبان‌های موجود باشد —
# آن رکورد فقط با انقضای طبیعی همان نسخهٔ پشتیبان خارج می‌شود.
#
# استفاده:
#   export BACKUP_DIR=/mnt/independent-backup/reqruitment
#   ./scripts/backup_rotate.sh --dry-run    # فهرست فایل‌های قابل‌حذف، بدون حذف
#   ./scripts/backup_rotate.sh              # حذف واقعی
#
# این اسکریپت فقط فایل‌های پشتیبان را مدیریت می‌کند — هرگز به پایگاه‌داده یا داده زنده دست نمی‌زند.
set -euo pipefail

: "${BACKUP_DIR:?BACKUP_DIR تنظیم نشده}"
RETENTION_MONTHS="${RETENTION_MONTHS:-12}"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "خطا: مقصد پشتیبان وجود ندارد: $BACKUP_DIR" >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] پشتیبان‌های قدیمی‌تر از ${RETENTION_MONTHS} ماه:"
  find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.dump' -o -name '*.dump.gpg' \) \
       -mtime "+$((RETENTION_MONTHS * 30))" -print
  echo "[dry-run] هیچ فایلی حذف نشد."
  exit 0
fi

COUNT=0
while IFS= read -r -d '' file; do
  echo "حذف پشتیبان منقضی: $file"
  rm -f -- "$file"
  COUNT=$((COUNT + 1))
done < <(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.dump' -o -name '*.dump.gpg' \) \
         -mtime "+$((RETENTION_MONTHS * 30))" -print0)

echo "$COUNT پشتیبان منقضی حذف شد (سیاست: ${RETENTION_MONTHS} ماه)."
