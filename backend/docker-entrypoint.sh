#!/bin/sh
set -e
# Migrações e papéis a cada subida (idempotente). Dados de demo só quando SEED_DEMO=1.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py bootstrap
  if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo ${SEED_DEMO_ARGS:-}
  fi
fi
exec "$@"
