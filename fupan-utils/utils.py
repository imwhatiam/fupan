import os
import random
import sqlite3
import requests
import pandas as pd
import baostock as bs
import chinese_calendar as calendar
from datetime import datetime, timedelta

INDUSTRY_NAME_DICT = {
    'J66货币金融服务': '货币金融',
    'G56航空运输业': '航空运输',
    'C36汽车制造业': '汽车制造',
    'K70房地产业': '房地产',
    'D46水的生产和供应业': '水产供应',
    'C31黑色金属冶炼和压延加工业': '钢铁冶炼',
    'D44电力、热力生产和供应业': '电力热力',
    'G54道路运输业': '道路运输',
    'G55水上运输业': '水运',
    'B07石油和天然气开采业': '油气开采',
    'J67资本市场服务': '资本市场',
    'C35专用设备制造业': '专用设备',
    'I63电信、广播电视和卫星传输服务': '电信传输',
    'C37铁路、船舶、航空航天和其他运输设备制造业': '运输设备',
    'E48土木工程建筑业': '土木建筑',
    'F51批发业': '批发业',
    'R87广播、电视、电影和录音制作业': '广播影视',
    'N78公共设施管理业': '公共设施',
    'L72商务服务业': '商务服务',
    'C15酒、饮料和精制茶制造业': '饮料制造',
    'C39计算机、通信和其他电子设备制造业': '电子设备',
    'C27医药制造业': '医药制造',
    'C26化学原料和化学制品制造业': '化工制品',
    'C38电气机械和器材制造业': '电气机械',
    'C40仪器仪表制造业': '仪器仪表',
    'C13农副食品加工业': '农副加工',
    'C20木材加工和木、竹、藤、棕、草制品业': '木材加工',
    'A04渔业': '渔业',
    'C22造纸和纸制品业': '造纸制品',
    'C18纺织服装、服饰业': '纺织服装',
    'A01农业': '农业',
    'C32有色金属冶炼和压延加工业': '有色冶炼',
    'C33金属制品业': '金属制品',
    'J69其他金融业': '其他金融',
    'B06煤炭开采和洗选业': '煤炭开采',
    'G53铁路运输业': '铁路运输',
    'I65软件和信息技术服务业': '软件服务',
    'N77生态保护和环境治理业': '生态环保',
    'C29橡胶和塑料制品业': '橡塑制品',
    'C17纺织业': '纺织业',
    'R89体育': '体育',
    'E47房屋建筑业': '房屋建筑',
    'C30非金属矿物制品业': '非金制品',
    'G58多式联运和运输代理业': '联运代理',
    'C14食品制造业': '食品制造',
    'E50建筑装饰、装修和其他建筑业': '建筑装饰',
    'C34通用设备制造业': '通用设备',
    'C42废弃资源综合利用业': '资源利用',
    'I64互联网和相关服务': '互联网',
    'R86新闻和出版业': '新闻出版',
    'G60邮政业': '邮政业',
    'H61住宿业': '住宿业',
    'B09有色金属矿采选业': '有色矿采',
    'F52零售业': '零售业',
    'Q84卫生': '卫生',
    'D45燃气生产和供应业': '燃气供应',
    'B11开采专业及辅助性活动': '开采辅助',
    'A05农、林、牧、渔专业及辅助性活动': '农林辅业',
    'B08黑色金属矿采选业': '黑色矿采',
    'C19皮革、毛皮、羽毛及其制品和制鞋业': '皮革制鞋',
    'P83教育': '教育',
    'C25石油、煤炭及其他燃料加工业': '燃料加工',
    'C28化学纤维制造业': '化学纤维',
    'C24文教、工美、体育和娱乐用品制造业': '文体用品',
    'S91综合': '综合',
    'M74专业技术服务业': '专业技术',
    'M73研究和试验发展': '研究发展',
    'C41其他制造业': '其他制造',
    'G59装卸搬运和仓储业': '仓储物流',
    'A03畜牧业': '畜牧业',
    'L71租赁业': '租赁业',
    'E49建筑安装业': '建筑安装',
    'J68保险业': '保险业',
    'C23印刷和记录媒介复制业': '印刷复制',
    'C21家具制造业': '家具制造',
    'R88文化艺术业': '文化艺术',
    'B10非金属矿采选业': '非金矿采',
    'H62餐饮业': '餐饮业',
    'M75科技推广和应用服务业': '科技推广',
    'A02林业': '林业',
    'C43金属制品、机械和设备修理业': '设备修理',
    'N76水利管理业': '水利管理',
    'O81机动车、电子产品和日用产品修理业': '产品修理',
}


def get_date_list(start_date_str='',
                  end_date_str=datetime.today().strftime('%Y-%m-%d')):

    if not start_date_str:
        return [end_date_str]

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    date_list = []
    while start_date <= end_date:
        date_list.append(start_date.strftime("%Y-%m-%d"))
        start_date += timedelta(days=1)

    return date_list


def is_weekend_or_holiday(date_str):

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

    if date_obj.isoweekday() > 5:
        error_msg = f"{date_str} is a weekend! {date_obj.strftime('%a')}"
        return True, error_msg

    on_holiday, holiday_name = calendar.get_holiday_detail(date_obj)
    if on_holiday:
        holiday_name == calendar.Holiday.labour_day.value
        error_msg = f"{date_str} is a holiday! {holiday_name}"
        return True, error_msg

    return False, ''


def is_monday(date_str):

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

    if date_obj.isoweekday() == 1:
        return True

    return False


def get_current_date_str():

    return datetime.today().strftime('%Y-%m-%d')


def get_latest_monday_date_str():

    today = datetime.today()
    offset = (today.isoweekday() - 1) % 7
    last_monday = today - timedelta(days=offset)
    return last_monday.strftime('%Y-%m-%d')


# stock industry data
def get_stock_industry_data_path(date_str=''):

    if not date_str:
        date_str = get_current_date_str()

    if not is_monday(date_str):
        date_str = get_latest_monday_date_str()

    return f'./stock_data/stock_industry_{date_str}.csv'


def download_stock_industry_data(date_str=''):

    print('Downloading stock industry data')

    file_path = get_stock_industry_data_path(date_str)
    if os.path.exists(file_path):
        print(f"Downloading stock industry data: {file_path} already exists")
        return file_path

    bs.login()
    rs = bs.query_stock_industry()

    industry_list = []
    while (rs.error_code == '0') & rs.next():
        industry_list.append(rs.get_row_data())
        result = pd.DataFrame(industry_list, columns=rs.fields)

    bs.logout()

    result.to_csv(file_path, index=False)
    print(f"Downloading stock industry data: data saved to {file_path}")
    return file_path


def read_stock_industry_data(date_str=''):

    print('Reading stock industry data')

    file_path = get_stock_industry_data_path(date_str)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Reading stock industry data: {file_path} not found")

    df = pd.read_csv(file_path)
    df = df[['code', 'industry']]
    df['code'] = df['code'].str.split('.').str[1]
    df['code'] = df['code'].astype(str)

    df.replace({'industry': INDUSTRY_NAME_DICT}, inplace=True)
    return df


# old stock data
def get_old_stock_data_path(start_date='', end_date=''):

    if not start_date:
        start_date = '2025-07-01'

    if not end_date:
        end_date = get_current_date_str()

    return f'./stock_data/old_stock_data_{start_date}_{end_date}.csv'


def download_old_stock_data(start_date='', end_date=''):

    if not start_date:
        start_date = '2025-07-01'

    if not end_date:
        end_date = get_current_date_str()

    try:
        from tqdm import tqdm
    except Exception:

        class _DummyPbar:

            def __init__(self, *args, **kwargs):
                pass

            def update(self, n=1):
                pass

            def close(self):
                pass

        def tqdm(iterable=None, *args, **kwargs):

            if iterable is None:
                return _DummyPbar()
            return iterable

    stock_industry_path = get_stock_industry_data_path()
    if not os.path.exists(stock_industry_path):
        stock_industry_path = download_stock_industry_data()

    industry_df = pd.read_csv(stock_industry_path)
    code_list = industry_df[industry_df['industry'].notnull()]['code'].tolist()

    bs.login()

    # iterate through each code and collect rows
    data_list = []
    for code in tqdm(code_list, desc="Processing codes"):
        rs = bs.query_history_k_data_plus(code,
                                          "date,code,open,close,pctChg,amount",
                                          start_date=start_date, end_date=end_date,
                                          frequency="d", adjustflag="2")
        row_pbar = tqdm(desc=f"Fetching rows for {code}", unit="row")
        while (rs.error_code == '0') and rs.next():
            data_list.append(rs.get_row_data())
            row_pbar.update(1)
        row_pbar.close()

    result = pd.DataFrame(data_list, columns=rs.fields)
    old_stock_data_path = get_old_stock_data_path(start_date, end_date)
    result.to_csv(old_stock_data_path, index=False)

    bs.logout()


def import_old_stock_data_to_sqlite(start_date='', end_date=''):

    if not start_date:
        start_date = '2025-07-01'

    if not end_date:
        end_date = get_current_date_str()

    # get base data
    old_stock_data_path = get_old_stock_data_path(start_date, end_date)
    stock_data = pd.read_csv(old_stock_data_path)

    stock_inustry_path = get_stock_industry_data_path()
    stock_industry = pd.read_csv(stock_inustry_path)

    # process stock industry
    stock_industry['code'] = stock_industry['code'].str[-6:]
    stock_industry['name'] = stock_industry['code_name']
    stock_industry['industry'] = stock_industry['industry'].map(INDUSTRY_NAME_DICT)
    industry_map = stock_industry[['code', 'name', 'industry']]

    # process stock data
    stock_data['code'] = stock_data['code'].str[-6:]

    # merge
    merged = stock_data.merge(industry_map, on='code', how='left')
    merged = merged[['date', 'code', 'name', 'open', 'close', 'pctChg', 'amount', 'industry']]

    conn = sqlite3.connect('./stock_data/stock_trade_info.sqlite3')
    cursor = conn.cursor()
    cursor.executescript(f"""
    CREATE TABLE stock_trade_info (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        date     TEXT    NOT NULL,
        code     TEXT    NOT NULL,
        name     TEXT    NOT NULL,
        open     REAL,
        close    REAL,
        pctChg   REAL,
        amount   REAL,
        industry TEXT,
        UNIQUE(date, code)
    );
    CREATE INDEX idx_date ON stock_trade_info(date);
    """)

    try:
        new_keys = set(zip(merged['date'], merged['code']))
        existing_keys = set(conn.execute("SELECT date, code FROM stock_trade_info").fetchall())
        duplicates = new_keys & existing_keys
        if duplicates:
            sample = list(duplicates)[:5]
            raise ValueError(f"发现重复数据，终止插入！重复 {len(duplicates)} 条，示例：{sample}")

        merged.to_sql('stock_trade_info', conn, if_exists='append', index=False)
        conn.commit()
        print(f"✅ 插入成功，共写入 {len(merged)} 条。")
    except ValueError as e:
        print(f"❌ {e}")
    finally:
        conn.close()


# sse stock data
def get_sse_stock_data_path(date_str=''):

    if not date_str:
        date_str = get_current_date_str()

    return f'./stock_data/sse_{date_str}.csv'


def download_sse_stock_data(date_str=''):

    print('Downloading SSE stock data')

    file_path = get_sse_stock_data_path(date_str)
    if os.path.exists(file_path):
        print(f'Downloading SSE stock data: {file_path} already exists')
        return file_path

    url = (
        "https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/equity"
        "?select=code,name,open,last,high,low,chg_rate,amount&begin=0&end=5000"
    )
    response = requests.get(url)
    resp_json = response.json()

    stock_list = resp_json.get('list')
    for stock in stock_list:
        stock.insert(0, date_str)
        stock[7] = float(stock[7])  # chg_rate to float

    columns = ['date', 'code', 'name', 'open', 'last', 'high', 'low', 'pctChg', 'amount']
    sse_stock_data_df = pd.DataFrame(stock_list, columns=columns)

    # save SSE stock data to CSV
    sse_stock_data_df.to_csv(file_path, index=False)
    print(f"Downloading SSE stock data: data saved to {file_path}")
    return file_path


def read_sse_stock_data(date_str=''):

    print('Reading SSE stock data')

    file_path = get_sse_stock_data_path(date_str)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Reading SSE stock data: {file_path} not found")

    df = pd.read_csv(file_path)
    df['amount'] = df['amount'].astype(float)
    df['code'] = df['code'].astype(str)
    return df


# szse stock data
def get_szse_stock_data_path(date_str=''):

    if not date_str:
        date_str = get_current_date_str()

    return f'./stock_data/szse_{date_str}.xlsx'


def download_szse_stock_data(date_str=''):

    print('Downloading SZSE stock data')

    file_path = get_szse_stock_data_path(date_str)
    if os.path.exists(file_path):
        print(f"Downloading SZSE stock data: {file_path} already exists")
        return file_path

    # get stock data from SZSE
    random_value = random.random()
    random_value = f"{random_value:.15f}"

    url = (
        "https://www.szse.cn/api/report/ShowReport"
        "?SHOWTYPE=xlsx&CATALOGID=1815_stock_snapshot&TABKEY=tab1&"
        f"txtBeginDate={date_str}&txtEndDate={date_str}&"
        "archiveDate=2024-02-01&random={random_value}"
    )
    response = requests.get(url)
    with open(file_path, 'wb') as f:
        f.write(response.content)

    print(f'Downloading SZSE stock data: data saved to {file_path}')
    return file_path


def read_szse_stock_data(date_str=''):

    print('Reading SZSE stock data')

    file_path = get_szse_stock_data_path(date_str)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Reading SZSE stock data: {file_path} not found")

    df = pd.read_excel(file_path)
    df = df[['交易日期', '证券代码', '证券简称', '开盘', '前收',
             '最高', '最低', '涨跌幅（%）', '成交金额(万元)']]
    df.columns = ['date', 'code', 'name', 'open', 'last',
                  'high', 'low', 'pctChg', 'amount']

    df['date'] = date_str
    df['code'] = df['code'].astype(str).str.zfill(6)
    df['pctChg'] = df['pctChg'].astype(float)
    df['amount'] = df['amount'].replace({',': ''}, regex=True).astype(float) * 10000
    df['code'] = df['code'].astype(str)

    return df
