"""
数据下载与读取服务
完整复现 utils.py 的数据层逻辑
"""
import os
import random
import requests
import pandas as pd
import chinese_calendar as calendar
from datetime import datetime, timedelta
from django.conf import settings


# ──────────────────────────────────────────────
# 日期工具
# ──────────────────────────────────────────────

def get_current_date_str():
    return datetime.today().strftime('%Y-%m-%d')


def is_weekend_or_holiday(date_str):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    if date_obj.isoweekday() > 5:
        return True, f"{date_str} 是周末（{date_obj.strftime('%a')}）"
    on_holiday, holiday_name = calendar.get_holiday_detail(date_obj)
    if on_holiday:
        return True, f"{date_str} 是节假日（{holiday_name}）"
    return False, ''


def is_monday(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date().isoweekday() == 1


def get_latest_monday_date_str():
    today = datetime.today()
    offset = (today.isoweekday() - 1) % 7
    return (today - timedelta(days=offset)).strftime('%Y-%m-%d')


def get_date_list(start_date_str='', end_date_str=''):
    if not end_date_str:
        end_date_str = get_current_date_str()
    if not start_date_str:
        return [end_date_str]
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = datetime.strptime(end_date_str, "%Y-%m-%d")
    result = []
    while start <= end:
        result.append(start.strftime("%Y-%m-%d"))
        start += timedelta(days=1)
    return result


# ──────────────────────────────────────────────
# 文件路径
# ──────────────────────────────────────────────


def get_sse_stock_data_path(date_str=''):
    if not date_str:
        date_str = get_current_date_str()
    return os.path.join(settings.STOCK_DATA_DIR, f'sse_{date_str}.csv')


def get_szse_stock_data_path(date_str=''):
    if not date_str:
        date_str = get_current_date_str()
    return os.path.join(settings.STOCK_DATA_DIR, f'szse_{date_str}.xlsx')


# ──────────────────────────────────────────────
# 下载函数
# ──────────────────────────────────────────────


def download_sse_stock_data(date_str=''):
    file_path = get_sse_stock_data_path(date_str)
    if os.path.exists(file_path):
        return file_path

    url = (
        "https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/equity"
        "?select=code,name,prev_close,last,chg_rate,amount&begin=0&end=5000"
    )
    response = requests.get(url, timeout=30)
    resp_json = response.json()

    raw_list = resp_json.get('list', [])
    stock_list = []
    for stock in raw_list:
        # 原始字段：code,name,prev_close,last,chg_rate,amount（6个）
        if not isinstance(stock, list) or len(stock) < 6:
            continue
        row = [date_str] + list(stock)   # 插入 date 作为第一列
        try:
            row[6] = float(row[6])        # amount（索引6，原始索引5）
        except (ValueError, TypeError, IndexError):
            row[6] = 0.0
        stock_list.append(row)

    columns = ['date', 'code', 'name', 'pre_close', 'close', 'pctChg', 'amount']
    df = pd.DataFrame(stock_list, columns=columns)
    df.to_csv(file_path, index=False)
    return file_path


def download_szse_stock_data(date_str=''):
    file_path = get_szse_stock_data_path(date_str)
    if os.path.exists(file_path):
        return file_path

    rv = f"{random.random():.15f}"
    url = (
        "https://www.szse.cn/api/report/ShowReport"
        f"?SHOWTYPE=xlsx&CATALOGID=1815_stock_snapshot&TABKEY=tab1"
        f"&txtBeginDate={date_str}&txtEndDate={date_str}"
        f"&archiveDate=2024-02-01&random={rv}"
    )
    response = requests.get(url, timeout=30)
    with open(file_path, 'wb') as f:
        f.write(response.content)
    return file_path


def download_all(date_str=''):
    """一次性下载当日全部数据，供 crontab 调用"""
    if not date_str:
        date_str = get_current_date_str()
    is_holiday, msg = is_weekend_or_holiday(date_str)
    if is_holiday:
        return {'skipped': True, 'reason': msg}
    download_sse_stock_data(date_str)
    download_szse_stock_data(date_str)
    return {'skipped': False, 'date': date_str}


def read_sse_stock_data(date_str=''):
    file_path = get_sse_stock_data_path(date_str)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"上证数据文件不存在: {file_path}")

    df = pd.read_csv(file_path)
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    df['code'] = df['code'].astype(str)
    return df


def read_szse_stock_data(date_str=''):
    file_path = get_szse_stock_data_path(date_str)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"深证数据文件不存在: {file_path}")

    df = pd.read_excel(file_path)
    df = df[['交易日期', '证券代码', '证券简称', '前收', '今收',
             '涨跌幅（%）', '成交金额(万元)']].copy()
    df.columns = ['date', 'code', 'name', 'pre_close', 'close', 'pctChg', 'amount']
    df['date'] = date_str
    df['code'] = df['code'].astype(str).str.zfill(6)
    df['pctChg'] = pd.to_numeric(df['pctChg'], errors='coerce').fillna(0)
    df['amount'] = (
        df['amount']
        .astype(str)
        .str.replace(',', '', regex=False)
        .pipe(pd.to_numeric, errors='coerce')
        .fillna(0)
        * 10000
    )
    return df
