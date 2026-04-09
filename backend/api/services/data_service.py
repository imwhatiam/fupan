"""
数据下载与读取服务
完整复现 utils.py 的数据层逻辑
"""
import os
import random
import threading
import requests
import pandas as pd
import baostock as bs
import chinese_calendar as calendar
from datetime import datetime, timedelta
from django.conf import settings

# baostock 全局锁，防止多线程并发调用导致 socket 冲突
_BS_LOCK = threading.Lock()


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

def get_stock_industry_data_path(date_str=''):
    if not date_str:
        date_str = get_current_date_str()
    if not is_monday(date_str):
        date_str = get_latest_monday_date_str()
    return os.path.join(settings.STOCK_DATA_DIR, f'stock_industry_{date_str}.csv')


def get_sse_stock_data_path(date_str=''):
    if not date_str:
        date_str = get_current_date_str()
    return os.path.join(settings.STOCK_DATA_DIR, f'sse_{date_str}.csv')


def get_szse_stock_data_path(date_str=''):
    if not date_str:
        date_str = get_current_date_str()
    return os.path.join(settings.STOCK_DATA_DIR, f'szse_{date_str}.xlsx')


# ──────────────────────────────────────────────
# 行业名称映射
# ──────────────────────────────────────────────

INDUSTRY_NAME_DICT = {
    'J66货币金融服务': '货币金融', 'G56航空运输业': '航空运输',
    'C36汽车制造业': '汽车制造', 'K70房地产业': '房地产业',
    'D46水的生产和供应业': '自来水', 'C31黑色金属冶炼和压延加工业': '黑色金属',
    'D44电力、热力生产和供应业': '电力热力', 'G54道路运输业': '道路运输',
    'G55水上运输业': '水上运输', 'B07石油和天然气开采业': '油气开采',
    'J67资本市场服务': '资本市场', 'C35专用设备制造业': '专用设备',
    'I63电信、广播电视和卫星传输服务': '电信广电',
    'C37铁路、船舶、航空航天和其他运输设备制造业': '运输设备',
    'E48土木工程建筑业': '土木工程', 'F51批发业': '批发业',
    'R87广播、电视、电影和录音制作业': '影视制作', 'N78公共设施管理业': '公共设施',
    'L72商务服务业': '商务服务', 'C15酒、饮料和精制茶制造业': '酒饮茶',
    'C39计算机、通信和其他电子设备制造业': '电子设备', 'C27医药制造业': '医药制造',
    'C26化学原料和化学制品制造业': '化工业', 'C38电气机械和器材制造业': '电气设备',
    'C40仪器仪表制造业': '仪器仪表', 'C13农副食品加工业': '农副食品',
    'C20木材加工和木、竹、藤、棕、草制品业': '木制品', 'A04渔业': '渔业',
    'C22造纸和纸制品业': '造纸业', 'C18纺织服装、服饰业': '纺织服装',
    'A01农业': '农业', 'C32有色金属冶炼和压延加工业': '有色金属',
    'C33金属制品业': '金属制品', 'J69其他金融业': '其他金融',
    'B06煤炭开采和洗选业': '煤炭开采', 'G53铁路运输业': '铁路运输',
    'I65软件和信息技术服务业': '软件信息', 'N77生态保护和环境治理业': '环保业',
    'C29橡胶和塑料制品业': '橡塑业', 'C17纺织业': '纺织业',
    'R89体育': '体育', 'E47房屋建筑业': '房屋建筑',
    'C30非金属矿物制品业': '非金属制品', 'G58多式联运和运输代理业': '运输代理',
    'C14食品制造业': '食品制造', 'E50建筑装饰、装修和其他建筑业': '建筑装饰',
    'C34通用设备制造业': '通用设备', 'C42废弃资源综合利用业': '资源回收',
    'I64互联网和相关服务': '互联网', 'R86新闻和出版业': '新闻出版',
    'G60邮政业': '邮政业', 'H61住宿业': '住宿业',
    'B09有色金属矿采选业': '有色矿采', 'F52零售业': '零售业',
    'Q84卫生': '卫生', 'D45燃气生产和供应业': '燃气供应',
    'B11开采专业及辅助性活动': '开采辅助', 'A05农、林、牧、渔专业及辅助性活动': '农林牧渔',
    'B08黑色金属矿采选业': '黑色矿采', 'C19皮革、毛皮、羽毛及其制品和制鞋业': '皮革业',
    'P83教育': '教育', 'C25石油、煤炭及其他燃料加工业': '燃料加工',
    'C28化学纤维制造业': '化纤业', 'C24文教、工美、体育和娱乐用品制造业': '文体用品',
    'S91综合': '综合', 'M74专业技术服务业': '专业技术',
    'M73研究和试验发展': '科研业', 'C41其他制造业': '其他制造',
    'G59装卸搬运和仓储业': '仓储物流', 'A03畜牧业': '畜牧业',
    'L71租赁业': '租赁业', 'E49建筑安装业': '建筑安装',
    'J68保险业': '保险业', 'C23印刷和记录媒介复制业': '印刷复制',
    'C21家具制造业': '家具制造', 'R88文化艺术业': '文化艺术',
    'B10非金属矿采选业': '非金属矿', 'H62餐饮业': '餐饮业',
    'M75科技推广和应用服务业': '科技服务', 'A02林业': '林业',
    'C43金属制品、机械和设备修理业': '设备修理', 'N76水利管理业': '水利管理',
    'O81机动车、电子产品和日用产品修理业': '产品修理',
}


# ──────────────────────────────────────────────
# 下载函数
# ──────────────────────────────────────────────

def download_stock_industry_data(date_str=''):
    file_path = get_stock_industry_data_path(date_str)
    if os.path.exists(file_path):
        return file_path

    # 使用全局锁，防止多线程同时调用 baostock 导致 socket 冲突
    with _BS_LOCK:
        # 双重检查：锁内再次确认文件是否已被其他线程写入
        if os.path.exists(file_path):
            return file_path

        bs.login()
        rs = bs.query_stock_industry()
        industry_list = []
        while (rs.error_code == '0') and rs.next():
            industry_list.append(rs.get_row_data())
            result = pd.DataFrame(industry_list, columns=rs.fields)
        bs.logout()

        if not industry_list:
            raise RuntimeError('baostock 未返回行业数据，请检查网络或稍后重试')

        result.to_csv(file_path, index=False)

    return file_path


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
    download_stock_industry_data(date_str)
    download_sse_stock_data(date_str)
    download_szse_stock_data(date_str)
    return {'skipped': False, 'date': date_str}


# ──────────────────────────────────────────────
# 读取函数
# ──────────────────────────────────────────────

def read_stock_industry_data(date_str=''):
    file_path = get_stock_industry_data_path(date_str)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"行业数据文件不存在: {file_path}")

    df = pd.read_csv(file_path)
    df = df[['code', 'industry']].copy()
    df['code'] = df['code'].str.split('.').str[1].astype(str)
    df.replace({'industry': INDUSTRY_NAME_DICT}, inplace=True)
    return df


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
