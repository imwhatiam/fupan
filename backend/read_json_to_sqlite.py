#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import pandas as pd
from pprint import pprint

JSON_PATH = "./stock_data/stock_industry.json"
CSV_PATH = "./stock_data/沪深京A股.csv"
DB_PATH = "./stock_trade_info.sqlite3"


def create_table(conn):
    create_sql = """
    CREATE TABLE IF NOT EXISTS stock_trade_info (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        date     TEXT    NOT NULL,
        code     TEXT    NOT NULL,
        name     TEXT    NOT NULL,
        pre_close     REAL,
        close    REAL,
        pctChg   REAL,
        amount   REAL,
        industry TEXT,
        UNIQUE(date, code)
    );
    """
    conn.execute(create_sql)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON stock_trade_info(date);")
    conn.commit()


def insert_record(conn, record):
    insert_sql = """
    INSERT INTO stock_trade_info
    (date, code, name, pre_close, close, pctChg, amount, industry)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn.execute(insert_sql, record)


def safe_float(value):
    """将值安全转换为 float，若无效则返回 None"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def load_stock_industry_mapping(csv_path):
    """
    CSV格式示例：
    序	代码	名称	最新	涨幅	换手	成交额	所属行业	总市值	流通市值
    "1"	'000001	"平安银行"	"11.11"	"-0.98%"	"0.10%"	"2.10亿"	"银行Ⅱ"	"2156亿元"	"2156亿元"
    "2"	'000002	"万  科Ａ"	"3.87"	"-2.03%"	"0.33%"	"1.25亿"	"房地产开发"	"462亿元"	"376亿元"
    "3"	'000003	"PT金田A"	"--"	"--"	"--"	"--"	"--"	"--"	"--"

    """
    if not os.path.exists(csv_path):
        print(f"警告: CSV文件不存在: {csv_path}")
        assert False

    df = pd.read_csv(csv_path, encoding='utf-16', sep='\t')
    data_list = df.to_dict(orient='records')

    mapping = {}
    for row in data_list:
        code = row['代码']
        code = code.strip("'")
        industry = row['所属行业']
        if industry == '--':
            continue
        mapping[code] = industry

    return mapping


def read_json_to_db(conn, stock_industry_map):

    if not os.path.exists(JSON_PATH):
        print(f"错误: JSON文件不存在: {JSON_PATH}")
        assert False

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        stocks = json.load(f)

    # [
    #   {
    #     "code": "000001",
    #     "name": "平安银行",
    #     "data": {
    #       "2025-08-21": [
    #         11.8,
    #         11.9,
    #         1477053291.9
    #       ],
    #       "2025-08-22": [
    #         11.9,
    #         11.81,
    #         1979461310.91
    #       ],

    total_records = 0
    for stock in stocks:

        code = stock.get("code")
        name = stock.get("name")
        if not code:
            print(f"警告: 股票{name}缺少code字段，跳过")
            continue
        if not name:
            print(f"警告: 股票{code}缺少name字段，跳过")
            continue

        data = stock.get("data")
        if not data:
            print(f"警告: 股票{code}缺少data字段，跳过")
            continue

        if code not in stock_industry_map:
            print(f"警告: 股票{code}没有行业信息，跳过")
            continue

        industry = stock_industry_map.get(code)
        if not industry:
            print(f"警告: 股票{code}没有行业信息，跳过")
            continue

        # process stock trade info by date
        for date_str, values in data.items():

            pre_close_price = safe_float(values[0] or 0)
            close_price = safe_float(values[1] or 0)
            amount = safe_float(values[2] or 0)

            if pre_close_price == 0 and close_price == 0 and amount == 0:
                # 未上市
                pct_chg = 0
            else:
                try:
                    pct_chg = (close_price - pre_close_price) / pre_close_price * 100
                except Exception as e:
                    print(e)
                    print(f"警告: {code} {date_str} 数据错误: {values}")
                    assert False

            record = (date_str, code, name, pre_close_price, close_price, pct_chg, amount, industry)
            insert_record(conn, record)
            total_records += 1

    conn.commit()
    print(f"JSON处理完成，共插入 {total_records} 条记录")
    return total_records


def main():

    pprint('start')

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    create_table(conn)

    # 加载行业映射
    stock_industry_map = load_stock_industry_mapping(CSV_PATH)

    # 处理JSON文件，插入新数据（自动使用行业映射）
    read_json_to_db(conn, stock_industry_map)

    conn.close()
    print("全部操作完成。")


if __name__ == "__main__":
    main()
