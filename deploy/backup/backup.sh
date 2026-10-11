#!/usr/bin/env bash
set -Eeuo pipefail

APP_DATA_DIR="${APP_DATA_DIR:-/var/lib/email-platform/data}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/lib/email-platform/backup}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

case "$APP_DATA_DIR:$BACKUP_ROOT" in
  *REPLACE_WITH*) echo "Replace deployment placeholders before running backup" >&2; exit 2 ;;
esac
[[ "$APP_DATA_DIR" = /* && "$BACKUP_ROOT" = /* ]] || { echo "Backup paths must be absolute" >&2; exit 2; }
[[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] || { echo "RETENTION_DAYS must be numeric" >&2; exit 2; }

DB_PATH="$APP_DATA_DIR/database.sqlite"
[[ -f "$DB_PATH" ]] || { echo "Database not found: $DB_PATH" >&2; exit 1; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_ROOT/$STAMP"
mkdir -p "$TARGET"
trap 'rm -rf -- "$TARGET"' ERR

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_PATH" ".backup '$TARGET/database.sqlite'"
else
  cp -- "$DB_PATH" "$TARGET/database.sqlite"
fi
for directory in eml attachments names; do
  if [[ -d "$APP_DATA_DIR/$directory" ]]; then
    tar -C "$APP_DATA_DIR" -czf "$TARGET/$directory.tar.gz" "$directory"
  fi
done

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -exec rm -rf -- {} +
printf 'Backup created: %s\n' "$TARGET"
