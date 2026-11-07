#!/bin/sh
# Cópia diária do Postgres (QAL-01). Agende no cron da VPS:
#   15 3 * * * /opt/petvila/deploy/backup.sh >> /var/log/petvila-backup.log 2>&1
set -e
cd "$(dirname "$0")/.."
mkdir -p backups
FILE="backups/petvila-$(date +%Y%m%d-%H%M).sql.gz"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$FILE"
find backups -name 'petvila-*.sql.gz' -mtime +14 -delete
echo "Backup gerado: $FILE"
