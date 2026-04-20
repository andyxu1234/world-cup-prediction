#!/bin/bash
set -e

echo "=== World Cup Prediction API Entry Point ==="

# 等待 MySQL 就绪
echo "[1/3] Waiting for MySQL at ${DB_HOST:-db}:${DB_PORT:-3306} ..."
MAX_WAIT=60
WAITED=0
until mysqladmin ping -h"${DB_HOST:-db}" -P"${DB_PORT:-3306}" -u"${DB_USER:-root}" -p"${DB_PASSWORD}" --silent 2>/dev/null; do
    WAITED=$((WAITED + 1))
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "ERROR: MySQL not ready after ${MAX_WAIT}s, aborting"
        exit 1
    fi
    sleep 1
done
echo "  MySQL is ready (${WAITED}s)"

# 执行 Alembic 迁移
echo "[2/3] Running database migrations..."
alembic upgrade head
echo "  Migrations done"

# 启动应用
echo "[3/3] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
