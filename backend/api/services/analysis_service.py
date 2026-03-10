"""
复盘分析服务 — 从 SQLite 读取数据进行分析
"""
import io
import base64
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from .db_service import get_trade_df


# ─────────────────────────────────────────────
# 内部工具
# ─────────────────────────────────────────────

def _filter_stocks(df, rise_or_fall, pct_chg_thresh=8.0, amount_thresh=8e8):
    if rise_or_fall == 'rise':
        filtered = df[(df['pctChg'] >= pct_chg_thresh) & (df['amount'] >= amount_thresh)]
        ascending = False
    else:
        filtered = df[(df['pctChg'] <= -pct_chg_thresh) & (df['amount'] >= amount_thresh)]
        ascending = True
    return filtered.sort_values('pctChg', ascending=ascending)[
        ['date', 'code', 'name', 'pctChg', 'amount', 'industry']
    ].copy()


def _df_to_records(df):
    records = []
    for _, row in df.iterrows():
        records.append({
            'date':     str(row['date']),
            'code':     str(row['code']),
            'name':     str(row['name']),
            'pctChg':   round(float(row['pctChg']), 2),
            'amount':   round(float(row['amount']) / 1e8, 2),
            'industry': str(row.get('industry', '')),
        })
    return records


def _industry_summary(df, total_amount, top_n=10):
    grouped = df.groupby('industry').agg(
        stock_count=('code', 'count'),
        avg_pctChg=('pctChg', 'mean'),
        _ind_amount=('amount', 'sum'),
    ).reset_index()

    grouped['industry_amount_ratio'] = grouped['_ind_amount'] / total_amount
    grouped.drop(columns=['_ind_amount'], inplace=True)
    grouped['score'] = (
        grouped['stock_count'] * grouped['avg_pctChg'] * grouped['industry_amount_ratio']
    )

    def make_stock_list(g):
        return [{'name': str(r['name']),
                 'pctChg': round(float(r['pctChg']), 2),
                 'amount': round(float(r['amount']) / 1e8, 2)}
                for _, r in g.iterrows()]

    stock_lists = df.groupby('industry').apply(make_stock_list)
    grouped['stocks'] = grouped['industry'].map(stock_lists)
    grouped = grouped.sort_values('score', ascending=False).head(top_n)

    result = []
    for _, row in grouped.iterrows():
        result.append({
            'industry':             str(row['industry']),
            'stock_count':          int(row['stock_count']),
            'avg_pctChg':           round(float(row['avg_pctChg']), 2),
            'industry_amount_ratio': round(float(row['industry_amount_ratio']), 6),
            'score':                round(float(row['score']), 6),
            'stocks':               row['stocks'],
        })
    return result


def _generate_chart_base64(summary_list, title):
    # plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti TC', 'Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    # plt.rcParams['axes.unicode_minus'] = False

    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    industries   = [r['industry']             for r in summary_list]
    stock_counts = [r['stock_count']           for r in summary_list]
    avg_pct_chgs = [r['avg_pctChg']            for r in summary_list]
    ratios       = [r['industry_amount_ratio'] for r in summary_list]

    x = np.arange(len(industries))
    width = 0.25

    count_norm = [v / 100 for v in stock_counts]
    pct_norm   = [v / 10  for v in avg_pct_chgs]

    fig, ax = plt.subplots(figsize=(14, 6))
    b1 = ax.bar(x - width, count_norm, width, label='stock_count/100')
    b2 = ax.bar(x,          pct_norm,  width, label='avg_pctChg/10')
    b3 = ax.bar(x + width,  ratios,    width, label='industry_amount_ratio')

    for i, rect in enumerate(b1):
        ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.005,
                str(stock_counts[i]), ha='center', va='bottom', fontsize=8)
    for i, rect in enumerate(b2):
        ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.005,
                f'{avg_pct_chgs[i]:.2f}', ha='center', va='bottom', fontsize=8)
    for i, rect in enumerate(b3):
        ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.005,
                f'{ratios[i]:.2%}', ha='center', va='bottom', fontsize=8)

    ax.set_title(title, fontsize=13)
    ax.set_ylabel('Normalized Value')
    ax.set_xticks(x)
    ax.set_xticklabels(industries, rotation=30, ha='right', fontsize=10)
    ax.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


# ─────────────────────────────────────────────
# 公开 API
# ─────────────────────────────────────────────

def get_fupan_data(date_str):
    """复盘主表：从 SQLite 读取数据并筛选涨跌≥8%、成交≥8亿"""
    df = get_trade_df(date_str)

    # 区分上证（代码 6 开头）和深证
    sse_df  = df[df['code'].str.startswith('6')].copy()
    szse_df = df[~df['code'].str.startswith('6')].copy()

    sse_rise  = _filter_stocks(sse_df,  'rise')
    sse_fall  = _filter_stocks(sse_df,  'fall')
    szse_rise = _filter_stocks(szse_df, 'rise')
    szse_fall = _filter_stocks(szse_df, 'fall')

    all_codes = pd.concat([sse_rise, sse_fall, szse_rise, szse_fall])['code'].tolist()

    return {
        'date': date_str,
        'sse':  {'rise': _df_to_records(sse_rise),  'fall': _df_to_records(sse_fall)},
        'szse': {'rise': _df_to_records(szse_rise), 'fall': _df_to_records(szse_fall)},
        'all_codes': all_codes,
        'stats': {
            'sse_rise_count':  len(sse_rise),
            'sse_fall_count':  len(sse_fall),
            'szse_rise_count': len(szse_rise),
            'szse_fall_count': len(szse_fall),
        },
    }


def get_industry_analysis(date_str):
    """行业分析：涨幅>5% 与 Top 10%，含柱状图 base64"""
    df = get_trade_df(date_str)
    total_amount = float(df['amount'].sum())

    all_sorted   = df.sort_values('pctChg', ascending=False)
    above_5pct   = all_sorted[all_sorted['pctChg'] > 5.0]
    top_10pct    = all_sorted.head(max(1, int(len(all_sorted) * 0.1)))

    above_5pct_summary = _industry_summary(above_5pct, total_amount)
    top_10pct_summary  = _industry_summary(top_10pct,  total_amount)

    return {
        'date': date_str,
        'total_amount_yi': round(total_amount / 1e8, 2),
        'above_5pct': {
            'summary':   above_5pct_summary,
            'chart_b64': _generate_chart_base64(above_5pct_summary, '涨幅超过5%行业分布'),
        },
        'top_10pct': {
            'summary':   top_10pct_summary,
            'chart_b64': _generate_chart_base64(top_10pct_summary, 'Top 10%涨幅行业分布'),
        },
    }
