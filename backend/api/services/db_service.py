"""
db_service.py

SQLite data-access layer for the daily market review system.

Responsibilities:
  - Define and initialise the ``stock_trade_info`` table.
  - Merge downloaded raw files (SSE CSV, SZSE XLSX, industry CSV) and persist
    them to the database via ``save_to_db()``.
  - Provide query helpers used by the analysis services.

Database file path is configured via ``settings.TRADE_DB_PATH``.

Industry data source priority (checked in save_to_db):
  1. 沪深京A股.csv  – uploaded manually to STOCK_DATA_DIR; columns "代码" and
     "所属行业" are used.  Stock codes in this file are prefixed with a leading
     apostrophe (e.g. ``'301683``); only the last six digits are kept.
  2. baostock CSV   – downloaded automatically via data_service when the
     上-file is absent.
"""

import os
import sqlite3

import pandas as pd
from django.conf import settings

from .data_service import (
    read_stock_industry_data,
    read_sse_stock_data,
    read_szse_stock_data,
    download_stock_industry_data,
    download_sse_stock_data,
    download_szse_stock_data,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Filename of the manually uploaded A-share list (placed in STOCK_DATA_DIR).
_HUSHEN_CSV = "沪深京A股.csv"


# ---------------------------------------------------------------------------
# Industry data helper
# ---------------------------------------------------------------------------

def _get_industry_df(date_str: str) -> pd.DataFrame:
    """Return a DataFrame with columns [code, industry] for merging.

    Checks for a manually uploaded ``沪深京A股.csv`` in STOCK_DATA_DIR first.
    If found, extracts the "代码" and "所属行业" columns and normalises the
    code values (strips the leading apostrophe and keeps the last 6 digits).

    Falls back to the baostock-sourced industry CSV when the file is absent.

    Args:
        date_str: Trading date string; passed to the baostock fallback path.

    Returns:
        DataFrame with exactly two columns: ``code`` (str) and ``industry`` (str).
    """
    hushen_path = os.path.join(settings.STOCK_DATA_DIR, _HUSHEN_CSV)

    if os.path.exists(hushen_path):
        df = pd.read_csv(hushen_path, dtype=str)

        # Normalise code: values look like "'301683" – keep the last 6 digits.
        df["code"] = (
            df["代码"]
            .str.strip()
            .str.replace("'", "", regex=False)   # strip leading apostrophe
            .str[-6:]                              # keep last 6 digits
            .str.zfill(6)                          # zero-pad just in case
        )
        df["industry"] = df["所属行业"].str.strip()
        return df[["code", "industry"]].copy()

    # Fallback: baostock-sourced CSV (downloaded automatically).
    return read_stock_industry_data(date_str)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_trade_info (
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
)
"""

_CREATE_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_date ON stock_trade_info(date)"
)


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Open and return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(settings.TRADE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the table and index if they do not already exist."""
    with _get_conn() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_INDEX_SQL)


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------

def save_to_db(date_str: str) -> int:
    """Download raw files for *date_str* and persist them to SQLite.

    Steps:
      1. Download industry CSV, SSE CSV, and SZSE XLSX (skips if cached).
      2. Read each file into a DataFrame and join on ``code``.
      3. Concatenate SSE and SZSE frames.
      4. Upsert all rows into ``stock_trade_info`` via INSERT OR REPLACE.
      5. Clear the in-memory cache for this date.

    Args:
        date_str: Trading date string in "YYYY-MM-DD" format.

    Returns:
        Number of rows written to the database.
    """
    init_db()

    # Download raw files (idempotent – skips if local files already exist).
    download_stock_industry_data(date_str)
    download_sse_stock_data(date_str)
    download_szse_stock_data(date_str)

    # Read and merge industry classification.
    # Prefers 沪深京A股.csv if present in STOCK_DATA_DIR; otherwise falls
    # back to the baostock-sourced CSV (downloaded above).
    industry_df = _get_industry_df(date_str)
    sse_df = read_sse_stock_data(date_str).merge(
        industry_df, on="code", how="left"
    )
    szse_df = read_szse_stock_data(date_str).merge(
        industry_df, on="code", how="left"
    )

    all_df = pd.concat([sse_df, szse_df], ignore_index=True)

    # Build the list of tuples for bulk insertion.
    rows = []
    for _, row in all_df.iterrows():
        rows.append((
            str(row["date"]),
            str(row["code"]),
            str(row["name"]),
            float(row["open"])   if pd.notna(row.get("open"))   else None,
            float(row["last"])   if pd.notna(row.get("last"))   else None,
            float(row["pctChg"]) if pd.notna(row.get("pctChg")) else None,
            float(row["amount"]) if pd.notna(row.get("amount")) else None,
            str(row["industry"]) if pd.notna(row.get("industry")) else "",
        ))

    with _get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stock_trade_info
                (date, code, name, open, close, pctChg, amount, industry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    return len(rows)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_trade_df(date_str: str) -> pd.DataFrame:
    """Return all trade rows for a single trading date as a DataFrame.

    Args:
        date_str: Date string in "YYYY-MM-DD" format.

    Returns:
        DataFrame with columns: id, date, code, name, open, close,
        pctChg, amount, industry.

    Raises:
        FileNotFoundError: if no rows exist for the requested date.
    """
    init_db()
    with _get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM stock_trade_info WHERE date=? ORDER BY code",
            conn,
            params=(date_str,),
        )

    if df.empty:
        raise FileNotFoundError(
            f"No data in the database for {date_str}."
        )
    return df


def get_available_dates() -> list:
    """Return a list of dates that have data, sorted in descending order."""
    init_db()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM stock_trade_info ORDER BY date DESC"
        ).fetchall()
    return [row["date"] for row in rows]


def has_date(date_str: str) -> bool:
    """Return True if at least one row exists for the given date."""
    init_db()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM stock_trade_info WHERE date=? LIMIT 1",
            (date_str,),
        ).fetchone()
    return row is not None
