#!/bin/bash
# 每日 17:00 自动下载股票数据并写入 SQLite
# crontab 配置示例：
#   0 17 * * 1-5 /path/to/fupan-system/scripts/cron_download.sh >> /var/log/fupan_cron.log 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== 开始每日数据更新 ====="
/root/.python-3.12-venv/bin/python /root/fupan/backend/manage.py download_stock_data
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== 更新完成 ====="
