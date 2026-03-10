"""
Hundred-day new high / new low analysis service.

Logic ported from the original Jupyter notebook (百日新高.ipynb).

For a given trading date D, a stock is defined as a "100-day new high" if its
closing price on D is greater than or equal to the maximum closing price over
the previous 99 trading days (i.e., the current close is the highest close
over a rolling 100-day window).

The same window logic applies inversely for "100-day new low".
"""

import io
import base64

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

from .db_service import _get_conn, init_db


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Rolling window length: previous N days are used to determine new high/low.
# Combined with today this represents a 100-trading-day range.
_ROLL_WINDOW = 99

# Number of recent dates shown on the ratio bar chart.
_CHART_DATES = 100

# Top-N industries displayed in the sector table.
_TOP_N_INDUSTRIES = 10


def _load_close_pivot(min_dates_needed: int) -> pd.DataFrame:
    """Load close prices from SQLite and return a wide pivot table.

    Rows are sorted trading dates; columns are stock codes.
    Only loads the most recent *min_dates_needed* dates to limit memory usage.

    Args:
        min_dates_needed: Minimum number of trading dates to load.

    Returns:
        DataFrame with shape (dates, codes) containing close prices.
        Dates are sorted ascending.
    """
    init_db()
    with _get_conn() as conn:
        # Fetch only the dates we need; subquery returns the N most recent dates.
        sql = """
            SELECT date, code, close
            FROM stock_trade_info
            WHERE date IN (
                SELECT DISTINCT date FROM stock_trade_info
                ORDER BY date DESC
                LIMIT ?
            )
            ORDER BY date ASC
        """
        df = pd.read_sql_query(sql, conn, params=(min_dates_needed,))

    if df.empty:
        return pd.DataFrame()

    # Pivot: rows=date, columns=code, values=close
    pivot = df.pivot(index="date", columns="code", values="close")
    pivot.sort_index(inplace=True)
    return pivot


def _load_industry_map() -> pd.Series:
    """Return a Series mapping stock code -> industry name.

    Uses the most recent date available to source the mapping.
    """
    init_db()
    with _get_conn() as conn:
        sql = """
            SELECT code, industry
            FROM stock_trade_info
            WHERE date = (SELECT MAX(date) FROM stock_trade_info)
        """
        df = pd.read_sql_query(sql, conn)

    if df.empty:
        return pd.Series(dtype=str)

    df.drop_duplicates(subset="code", inplace=True)
    return df.set_index("code")["industry"]


def _load_stock_names() -> pd.Series:
    """Return a Series mapping stock code -> stock name."""
    init_db()
    with _get_conn() as conn:
        sql = """
            SELECT code, name
            FROM stock_trade_info
            WHERE date = (SELECT MAX(date) FROM stock_trade_info)
        """
        df = pd.read_sql_query(sql, conn)

    if df.empty:
        return pd.Series(dtype=str)

    df.drop_duplicates(subset="code", inplace=True)
    return df.set_index("code")["name"]


def _compute_high_low_flags(pivot: pd.DataFrame):
    """Compute boolean flags for 100-day new high and new low per date/code.

    For date at row i, a stock is a new-high if:
        close[i] >= max(close[i - ROLL_WINDOW : i])   (previous 99 days)

    Args:
        pivot: Wide DataFrame (date x code) of close prices.

    Returns:
        Tuple (new_high_df, new_low_df), each a boolean DataFrame with the
        same shape as *pivot*.  Cells with insufficient history are False.
    """
    # shift(1).rolling(_ROLL_WINDOW) gives the max of the PREVIOUS 99 days,
    # excluding today, which matches the notebook's sliding-window logic.
    rolling_max = (
        pivot.shift(1)
        .rolling(window=_ROLL_WINDOW, min_periods=_ROLL_WINDOW)
        .max()
    )
    rolling_min = (
        pivot.shift(1)
        .rolling(window=_ROLL_WINDOW, min_periods=_ROLL_WINDOW)
        .min()
    )

    # A stock is a new high/low only when rolling stats are available.
    has_history = rolling_max.notna()

    new_high = (pivot >= rolling_max) & has_history
    new_low = (pivot <= rolling_min) & has_history

    return new_high, new_low


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_hundred_day_analysis(date_str: str) -> dict:
    """Compute 100-day new high / low analysis for the given trading date.

    Args:
        date_str: Target date in "YYYY-MM-DD" format.

    Returns:
        A dict with keys:
          - "date": the input date_str
          - "new_high_sectors": list of sector dicts (sorted by stock count)
          - "new_low_sectors":  list of sector dicts (sorted by stock count)
          - "ratio_chart_b64": base-64 encoded PNG of the ratio bar chart
          - "total_stocks":     total number of stocks on the target date
          - "high_count":       new-high stock count on the target date
          - "low_count":        new-low stock count on the target date

    Raises:
        FileNotFoundError: if there is no data for the requested date.
    """
    # We need ROLL_WINDOW + CHART_DATES trading days of data so that
    # the chart shows up to CHART_DATES data points with full history each.
    dates_needed = _ROLL_WINDOW + _CHART_DATES

    pivot = _load_close_pivot(dates_needed)

    if pivot.empty:
        raise FileNotFoundError("No trade data found in the database.")

    if date_str not in pivot.index:
        raise FileNotFoundError(
            f"No data for {date_str}. Available range: "
            f"{pivot.index[0]} – {pivot.index[-1]}"
        )

    industry_map = _load_industry_map()
    name_map = _load_stock_names()

    new_high_df, new_low_df = _compute_high_low_flags(pivot)

    # ------------------------------------------------------------------
    # 1. Sector table for the target date
    # ------------------------------------------------------------------
    target_highs = _build_sector_table(
        new_high_df, date_str, industry_map, name_map, ascending=False
    )
    target_lows = _build_sector_table(
        new_low_df, date_str, industry_map, name_map, ascending=True
    )

    # Total stocks with close price on the target date
    total_stocks = int(pivot.loc[date_str].notna().sum())
    high_count = int(new_high_df.loc[date_str].sum()) if date_str in new_high_df.index else 0
    low_count = int(new_low_df.loc[date_str].sum()) if date_str in new_low_df.index else 0

    # ------------------------------------------------------------------
    # 2. Ratio bar chart (last CHART_DATES trading dates with full history)
    # ------------------------------------------------------------------
    # Dates that have valid (non-null) rolling stats are dates with full history.
    valid_dates = new_high_df.dropna(how="all").index.tolist()

    chart_b64 = _generate_ratio_chart(
        pivot, new_high_df, new_low_df, valid_dates, date_str
    )

    return {
        "date": date_str,
        "new_high_sectors": target_highs,
        "new_low_sectors": target_lows,
        "ratio_chart_b64": chart_b64,
        "total_stocks": total_stocks,
        "high_count": high_count,
        "low_count": low_count,
    }


def _build_sector_table(
    flag_df: pd.DataFrame,
    date_str: str,
    industry_map: pd.Series,
    name_map: pd.Series,
    ascending: bool,
) -> list:
    """Build a list of sector dicts for the given boolean flag DataFrame.

    Args:
        flag_df:      Boolean DataFrame (date x code).
        date_str:     Target date string.
        industry_map: Series mapping code -> industry.
        name_map:     Series mapping code -> stock name.
        ascending:    If True, sort sectors by count ascending (new-low order).

    Returns:
        List of dicts, each representing one sector, sorted and limited to
        TOP_N_INDUSTRIES entries.
    """
    if date_str not in flag_df.index:
        return []

    # Codes that hit the flag on target date
    codes_on_date = flag_df.loc[date_str]
    flagged_codes = codes_on_date[codes_on_date].index.tolist()

    if not flagged_codes:
        return []

    # Group by industry
    sector_count: dict = {}
    sector_stocks: dict = {}

    for code in flagged_codes:
        industry = industry_map.get(code, "")
        if not industry or industry == "nan":
            continue
        name = name_map.get(code, code)
        sector_count[industry] = sector_count.get(industry, 0) + 1
        sector_stocks.setdefault(industry, []).append(name)

    # Sort by count
    sorted_sectors = sorted(
        sector_count.items(),
        key=lambda x: x[1],
        reverse=(not ascending),
    )[:_TOP_N_INDUSTRIES]

    result = []
    for industry, count in sorted_sectors:
        result.append(
            {
                "industry": industry,
                "count": count,
                "stocks": sector_stocks.get(industry, []),
            }
        )

    return result


def _generate_ratio_chart(
    pivot: pd.DataFrame,
    new_high_df: pd.DataFrame,
    new_low_df: pd.DataFrame,
    valid_dates: list,
    end_date_str: str,
) -> str:
    """Generate a bar chart of 100-day new-high / new-low ratio over time.

    The chart mirrors the notebook (Cell 7):
      - Red bars: new-high count / total stocks (positive)
      - Green bars: new-low count / total stocks (negative)

    Args:
        pivot:        Wide DataFrame of close prices.
        new_high_df:  Boolean DataFrame for new-high flags.
        new_low_df:   Boolean DataFrame for new-low flags.
        valid_dates:  List of dates that have full 99-day history.
        end_date_str: The rightmost date to show on the chart.

    Returns:
        Base-64 encoded PNG string.
    """
    # Use only valid dates up to end_date_str
    chart_dates = [d for d in valid_dates if d <= end_date_str]
    chart_dates = chart_dates[-_CHART_DATES:]  # cap at CHART_DATES bars

    if not chart_dates:
        # Return a small placeholder image when there is not enough data yet
        return _placeholder_chart_b64(
            "Insufficient history for ratio chart. "
            "At least 100 trading days of data are required."
        )

    date_labels = [d[2:] for d in chart_dates]  # "YY-MM-DD" abbreviated

    high_ratios = []
    low_ratios = []

    for date in chart_dates:
        total = int(pivot.loc[date].notna().sum())
        if total == 0:
            high_ratios.append(0.0)
            low_ratios.append(0.0)
            continue
        high_count = int(new_high_df.loc[date].sum()) if date in new_high_df.index else 0
        low_count = int(new_low_df.loc[date].sum()) if date in new_low_df.index else 0
        high_ratios.append(high_count / total * 100)
        low_ratios.append(-low_count / total * 100)

    # Font setup for Chinese labels on macOS / Linux
    # plt.rcParams["font.sans-serif"] = [
    #     "PingFang SC", "Heiti TC", "Arial Unicode MS", "SimHei", "DejaVu Sans"
    # ]
    # plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.sans-serif"] = [
        "WenQuanYi Micro Hei", "PingFang SC", "SimHei", "DejaVu Sans"
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(16, 5))

    ax.set_title("100-Day New High / New Low Ratio", fontsize=14, fontweight="bold")
    ax.set_xlabel(f"Last {len(chart_dates)} trading days", fontsize=11)
    ax.set_ylabel("Ratio of total stocks (%)", fontsize=11)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.2f%%"))

    # Reduce x-tick density when there are many bars
    step = max(1, len(chart_dates) // 10)
    tick_positions = range(0, len(date_labels), step)
    ax.set_xticks(list(tick_positions))
    ax.set_xticklabels([date_labels[i] for i in tick_positions], fontsize=9)
    ax.tick_params(axis="y", labelsize=9)

    x = np.arange(len(date_labels))
    ax.bar(x, high_ratios, label="100-day High Ratio", color="#cf1322", alpha=0.85)
    ax.bar(x, low_ratios, label="100-day Low Ratio", color="#389e0d", alpha=0.85)
    ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")

    ax.legend(fontsize=10, loc="upper left")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _placeholder_chart_b64(message: str) -> str:
    """Return a simple placeholder PNG with a text message."""
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
