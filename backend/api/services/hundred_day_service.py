"""
hundred_day_service.py

百日新高 / 新低分析服务。

算法说明
--------
对于目标交易日 D，若某只股票在 D 的收盘价 >= 其前 99 个交易日收盘价的最大值，
则将其标记为「百日新高」；反之若 <= 最小值，则标记为「百日新低」。

滚动窗口使用 shift(1).rolling(99)，即当天的收盘价不参与窗口计算，
保持「用过去 99 天来判断今天」的语义。

缺失值处理
----------
对于以下两种情况，历史收盘价字段在 pivot 表中为 NaN：

  1. 新上市股票：上市日之前无任何数据；
  2. 停牌股票：停牌期间无数据。

处理策略：在计算滚动窗口 **之前**，用 0 填充历史缺失值（fillna(0)），
从而使每只股票始终拥有完整的 99 天参考窗口，避免因数据不足而被跳过。

今日收盘价本身 **不做填充**：若某只股票当天停牌（pivot 中为 NaN），
则 NaN 与任何数值的比较结果都为 False，自然地将其排除在新高/新低判断之外。
"""

import base64
import io
from collections import Counter, defaultdict

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

matplotlib.use("Agg")

from .db_service import _get_conn, init_db  # noqa: E402


# ---------------------------------------------------------------------------
# 模块级常量
# ---------------------------------------------------------------------------

# 滚动窗口宽度：使用今天之前的 N 天收盘价作为参考，与今天合计构成 100 天。
_ROLL_WINDOW = 99

# 比率走势图最多展示的交易日数量。
_CHART_DATES = 100

# 行业聚合表最多展示的行业数量。
_TOP_N_INDUSTRIES = 10


# ---------------------------------------------------------------------------
# 数据库读取层
# ---------------------------------------------------------------------------

def _load_close_pivot(min_dates_needed: int) -> pd.DataFrame:
    """从 SQLite 读取收盘价并返回宽表（pivot）。

    行为交易日期（升序），列为股票代码，值为收盘价。
    只读取最近 min_dates_needed 个交易日，以控制内存用量。

    对于某只股票在某个交易日没有数据的情况（新上市/停牌），
    pivot 对应位置自动为 NaN，由 _compute_high_low_flags 统一处理。

    Parameters
    ----------
    min_dates_needed : int
        至少需要加载的交易日数量（= _ROLL_WINDOW + _CHART_DATES = 199）。

    Returns
    -------
    pd.DataFrame
        shape = (交易日数, 股票数)，index 为日期字符串，columns 为股票代码。
        数据库为空时返回空 DataFrame。
    """
    init_db()
    with _get_conn() as conn:
        # 子查询先取最近 N 个不重复交易日，主查询再过滤，避免全表扫描。
        sql = """
            SELECT date, code, close
            FROM stock_trade_info
            WHERE date IN (
                SELECT DISTINCT date
                FROM stock_trade_info
                ORDER BY date DESC
                LIMIT ?
            )
            ORDER BY date ASC
        """
        df = pd.read_sql_query(sql, conn, params=(min_dates_needed,))

    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot(index="date", columns="code", values="close")
    pivot.sort_index(inplace=True)
    return pivot


def _load_stock_metadata() -> tuple:
    """一次查询同时返回行业映射和股票名称映射。

    查询来源为数据库中最新一个交易日的记录，以保证行业/名称信息最新。
    将两个查询合并为一次 DB 往返，减少连接开销。

    Returns
    -------
    tuple[pd.Series, pd.Series]
        (industry_map, name_map)，均以股票代码为 index。
        数据库为空时返回两个空 Series。
    """
    init_db()
    with _get_conn() as conn:
        sql = """
            SELECT code, name, industry
            FROM stock_trade_info
            WHERE date = (SELECT MAX(date) FROM stock_trade_info)
        """
        df = pd.read_sql_query(sql, conn)

    if df.empty:
        empty = pd.Series(dtype=str)
        return empty, empty

    df = df.drop_duplicates(subset="code").set_index("code")
    return df["industry"], df["name"]


# ---------------------------------------------------------------------------
# 核心计算
# ---------------------------------------------------------------------------

def _compute_high_low_flags(pivot: pd.DataFrame) -> tuple:
    """计算每个日期、每只股票是否触发百日新高或新低的布尔标志。

    算法步骤
    --------
    1. 用 0 填充历史缺失值（新上市/停牌日），确保每只股票的历史窗口完整。
    2. 对填充后的 pivot 执行 shift(1)，使第 i 行的滚动窗口对应「今天之前的
       99 天」，不含今天本身。
    3. 计算滚动最大值（prev_99_max）和最小值（prev_99_min）。
    4. 用原始 pivot（未填充）判断今天是否有真实收盘价（has_close_today）；
       停牌股当天 NaN 与任何数值比较均返回 False，自然被排除。
    5. 同时满足「今天有收盘价」且「超越滚动极值」即为新高/新低。

    Parameters
    ----------
    pivot : pd.DataFrame
        _load_close_pivot 返回的宽表（未做任何填充）。

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (new_high_df, new_low_df)，与 pivot 同形状的布尔 DataFrame。
        True = 该日该股触发新高（或新低）。
    """
    # ── 步骤 1：填充历史缺失值 ────────────────────────────────────────────
    # 只对历史数据填 0，今日收盘价保留原始 NaN 以便后续过滤停牌股。
    pivot_filled = pivot.fillna(0)

    # ── 步骤 2 & 3：计算前 99 天的滚动极值 ──────────────────────────────
    # shift(1) 将当天排除在外；min_periods=_ROLL_WINDOW 要求窗口恰好满 99
    # 天才输出结果（fillna(0) 后所有历史位置均非 NaN，满足此条件）。
    prev_99_max = (
        pivot_filled
        .shift(1)
        .rolling(window=_ROLL_WINDOW, min_periods=_ROLL_WINDOW)
        .max()
    )
    prev_99_min = (
        pivot_filled
        .shift(1)
        .rolling(window=_ROLL_WINDOW, min_periods=_ROLL_WINDOW)
        .min()
    )

    # ── 步骤 4：今天是否有真实收盘价（停牌 = False）─────────────────────
    has_close_today = pivot.notna()

    # ── 步骤 5：综合判断 ──────────────────────────────────────────────────
    new_high = (pivot >= prev_99_max) & has_close_today
    new_low = (pivot <= prev_99_min) & has_close_today

    return new_high, new_low


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def get_hundred_day_analysis(date_str: str) -> dict:
    """计算指定交易日的百日新高 / 新低分析结果。

    Parameters
    ----------
    date_str : str
        目标交易日，格式为 "YYYY-MM-DD"。

    Returns
    -------
    dict
        包含以下键：
        - "date"             : 输入的 date_str
        - "new_high_sectors" : 百日新高行业列表（按股票数量降序）
        - "new_low_sectors"  : 百日新低行业列表（按股票数量降序）
        - "ratio_chart_b64"  : 比率走势图（base64 编码 PNG）
        - "total_stocks"     : 目标日全市场有收盘价的股票总数
        - "high_count"       : 目标日百日新高股票数
        - "low_count"        : 目标日百日新低股票数

    Raises
    ------
    FileNotFoundError
        数据库为空，或指定日期无数据时抛出。
    """
    # ── 步骤 1：加载数据 ──────────────────────────────────────────────────
    # 需要 _ROLL_WINDOW + _CHART_DATES 天的数据，以保证每个图表柱都有完整历史。
    dates_needed = _ROLL_WINDOW + _CHART_DATES
    pivot = _load_close_pivot(dates_needed)

    if pivot.empty:
        raise FileNotFoundError("数据库中没有交易数据，请先导入数据。")
    if date_str not in pivot.index:
        raise FileNotFoundError(
            f"日期 {date_str} 无数据。"
            f"可用范围：{pivot.index[0]} — {pivot.index[-1]}"
        )

    industry_map, name_map = _load_stock_metadata()

    # ── 步骤 2：计算全时间段的新高 / 新低标志 ────────────────────────────
    new_high_df, new_low_df = _compute_high_low_flags(pivot)

    # ── 步骤 3：提取目标日的汇总指标 ─────────────────────────────────────
    total_stocks = int(pivot.loc[date_str].notna().sum())
    high_count = int(new_high_df.loc[date_str].sum())
    low_count = int(new_low_df.loc[date_str].sum())

    # ── 步骤 4：构建目标日的行业聚合表 ───────────────────────────────────
    new_high_sectors = _build_sector_table(
        new_high_df, date_str, industry_map, name_map
    )
    new_low_sectors = _build_sector_table(
        new_low_df, date_str, industry_map, name_map
    )

    # ── 步骤 5：生成比率走势图 ───────────────────────────────────────────
    # 只有历史窗口满 99 天的交易日才出现在图表中（dropna 过滤掉早期数据）。
    dates_with_history = new_high_df.dropna(how="all").index.tolist()
    ratio_chart_b64 = _generate_ratio_chart(
        pivot, new_high_df, new_low_df, dates_with_history, date_str
    )

    return {
        "date": date_str,
        "new_high_sectors": new_high_sectors,
        "new_low_sectors": new_low_sectors,
        "ratio_chart_b64": ratio_chart_b64,
        "total_stocks": total_stocks,
        "high_count": high_count,
        "low_count": low_count,
    }


# ---------------------------------------------------------------------------
# 结果构建器
# ---------------------------------------------------------------------------

def _build_sector_table(
    flag_df: pd.DataFrame,
    date_str: str,
    industry_map: pd.Series,
    name_map: pd.Series,
) -> list:
    """从布尔标志 DataFrame 中构建按行业聚合的股票列表。

    对 flag_df 中目标日为 True 的股票，按行业分组统计数量，
    并收集每个行业内的股票名称列表，返回前 _TOP_N_INDUSTRIES 个行业。

    Parameters
    ----------
    flag_df : pd.DataFrame
        _compute_high_low_flags 返回的布尔 DataFrame（日期 × 股票代码）。
    date_str : str
        目标日期字符串。
    industry_map : pd.Series
        股票代码 → 行业名称的映射。
    name_map : pd.Series
        股票代码 → 股票名称的映射。

    Returns
    -------
    list[dict]
        每个元素包含：
        - "industry" : 行业名称
        - "count"    : 该行业触发标志的股票数量
        - "stocks"   : 股票名称列表
        按 count 降序排列，最多返回 _TOP_N_INDUSTRIES 条。
    """
    if date_str not in flag_df.index:
        return []

    # 取出目标日触发标志（True）的所有股票代码。
    row = flag_df.loc[date_str]
    flagged_codes = row[row].index.tolist()

    if not flagged_codes:
        return []

    # 使用 Counter 和 defaultdict 按行业聚合，语义比手工 dict.get 更清晰。
    industry_counter: Counter = Counter()
    industry_stocks: dict = defaultdict(list)

    for code in flagged_codes:
        industry = industry_map.get(code, "")
        # 跳过行业信息缺失或异常的股票。
        if not industry or industry == "nan":
            continue
        industry_counter[industry] += 1
        industry_stocks[industry].append(name_map.get(code, code))

    # most_common 内部已按 count 降序排列，直接取前 N 即可。
    top_sectors = industry_counter.most_common(_TOP_N_INDUSTRIES)
    return [
        {
            "industry": industry,
            "count": count,
            "stocks": industry_stocks[industry],
        }
        for industry, count in top_sectors
    ]


# ---------------------------------------------------------------------------
# 图表生成
# ---------------------------------------------------------------------------

def _generate_ratio_chart(
    pivot: pd.DataFrame,
    new_high_df: pd.DataFrame,
    new_low_df: pd.DataFrame,
    dates_with_history: list,
    end_date_str: str,
) -> str:
    """生成百日新高 / 新低占比的双向柱状图。

    图表复现 Notebook Cell 7 的逻辑：
    - 红色柱（正方向）：当日新高数量 / 全市场股票总数
    - 绿色柱（负方向）：当日新低数量 / 全市场股票总数

    Parameters
    ----------
    pivot : pd.DataFrame
        收盘价宽表，用于计算每日全市场股票总数。
    new_high_df : pd.DataFrame
        新高布尔标志 DataFrame。
    new_low_df : pd.DataFrame
        新低布尔标志 DataFrame。
    dates_with_history : list[str]
        已有满 99 天历史的交易日列表（升序）。
    end_date_str : str
        图表最右侧日期（= 目标交易日）。

    Returns
    -------
    str
        Base64 编码的 PNG 图片字符串。
        数据不足时返回包含提示文字的占位图。
    """
    # 只取 end_date_str 及之前、有完整历史的日期，最多显示 _CHART_DATES 根柱。
    chart_dates = [d for d in dates_with_history if d <= end_date_str]
    chart_dates = chart_dates[-_CHART_DATES:]

    if not chart_dates:
        return _placeholder_chart_b64(
            "数据不足，至少需要 100 个交易日的数据才能生成走势图。"
        )

    # 逐日计算新高 / 新低占全市场的比率。
    high_ratios = []
    low_ratios = []
    for date in chart_dates:
        total = int(pivot.loc[date].notna().sum())
        if total == 0:
            high_ratios.append(0.0)
            low_ratios.append(0.0)
            continue
        highs = (
            int(new_high_df.loc[date].sum())
            if date in new_high_df.index
            else 0
        )
        lows = (
            int(new_low_df.loc[date].sum())
            if date in new_low_df.index
            else 0
        )
        high_ratios.append(highs / total * 100)
        # 新低比率取负值，绘制在 x 轴下方，便于直观对比。
        low_ratios.append(-lows / total * 100)

    # "YY-MM-DD" 缩写，减少 x 轴文字拥挤。
    date_labels = [d[2:] for d in chart_dates]

    plt.rcParams["font.sans-serif"] = [
        "WenQuanYi Micro Hei", "PingFang SC", "SimHei", "DejaVu Sans"
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.set_title(
        "百日新高 / 新低占比走势", fontsize=14, fontweight="bold"
    )
    ax.set_xlabel(f"最近 {len(chart_dates)} 个交易日", fontsize=11)
    ax.set_ylabel("占全市场股票比例 (%)", fontsize=11)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.2f%%"))

    # 柱子较多时降低 x 轴刻度密度，避免文字重叠。
    step = max(1, len(chart_dates) // 10)
    tick_positions = list(range(0, len(date_labels), step))
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        [date_labels[i] for i in tick_positions], fontsize=9
    )
    ax.tick_params(axis="y", labelsize=9)

    x = np.arange(len(date_labels))
    ax.bar(x, high_ratios, label="百日新高占比", color="#cf1322", alpha=0.85)
    ax.bar(x, low_ratios, label="百日新低占比", color="#389e0d", alpha=0.85)
    # 零轴参考线，便于区分新高与新低区域。
    ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")
    ax.legend(fontsize=10, loc="upper left")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _placeholder_chart_b64(message: str) -> str:
    """生成仅包含提示文字的占位图，数据不足时返回给前端。

    Parameters
    ----------
    message : str
        显示在图片中央的提示文字。

    Returns
    -------
    str
        Base64 编码的 PNG 字符串。
    """
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.text(
        0.5, 0.5, message,
        ha="center", va="center", fontsize=12, color="#888",
        transform=ax.transAxes,
    )
    ax.axis("off")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
