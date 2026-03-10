#!/bin/bash
# 每日 17:00 自动下载股票数据并写入 SQLite
# crontab 配置示例：
#   0 17 * * 1-5 /path/to/fupan-system/scripts/cron_download.sh >> /var/log/fupan_cron.log 2>&1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

# 优先使用项目虚拟环境
if [ -f "$BACKEND_DIR/../venv/bin/python" ]; then
    PYTHON="$BACKEND_DIR/../venv/bin/python"
else
    PYTHON="${PYTHON_BIN:-python3}"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== 开始每日数据更新 ====="
cd "$BACKEND_DIR"
$PYTHON manage.py download_stock_data
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== 更新完成 ====="
