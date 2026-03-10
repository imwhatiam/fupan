"""
python manage.py download_stock_data [--date 2026-02-26]
供 crontab 调用：下载三个原始文件 + 存入 SQLite
"""
from django.core.management.base import BaseCommand
from api.services.db_service import save_to_db
from api.services.data_service import (
    get_current_date_str, is_weekend_or_holiday
)


class Command(BaseCommand):
    help = "下载股票数据并写入 stock_trade_info.sqlite3（默认今日）"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="指定日期 YYYY-MM-DD")

    def handle(self, *args, **options):
        date_str = options["date"] or get_current_date_str()
        is_hol, reason = is_weekend_or_holiday(date_str)
        if is_hol:
            self.stdout.write(self.style.WARNING(f"跳过：{reason}"))
            return
        self.stdout.write(f"[{date_str}] 开始下载并写入数据库...")
        count = save_to_db(date_str)
        self.stdout.write(self.style.SUCCESS(f"[{date_str}] 完成，写入 {count} 条记录"))
