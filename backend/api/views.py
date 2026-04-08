"""
views.py

Django REST Framework API views for the daily market review system.

Endpoints:
  POST /api/init/          – Page initialisation; resolves starting date.
  POST /api/upload/        – Upload a CSV file to the stock_data directory.
  GET  /api/fupan/         – Daily review table (large movers).
  GET  /api/industry/      – Sector analysis with charts.
  GET  /api/hundred-day/   – 100-day new high / new low analysis.
  GET  /api/dates/         – List of dates available in the database.
  GET  /api/health/        – Health check.

All GET analysis endpoints use a 12-hour in-memory cache keyed by date.
"""

import os
import glob
import threading
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import data_service, analysis_service
from .services import db_service
from .services import hundred_day_service

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Cache time-to-live: 12 hours (analysis results rarely change intraday).
CACHE_TTL = 60 * 60 * 12

# Tracks which dates are currently being downloaded in background threads.
# Prevents duplicate downloads when React StrictMode triggers double-mount.
_DOWNLOAD_IN_PROGRESS: set = set()
_DOWNLOAD_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _do_download_and_save(date_str: str) -> None:
    """Download raw data files and write them to the SQLite database.

    Intended to run in a daemon background thread so the HTTP response
    is not blocked.  Uses a set + lock to ensure only one thread per date
    is active at a time (guards against React StrictMode double-invocation).

    Args:
        date_str: Trading date string in "YYYY-MM-DD" format.
    """
    with _DOWNLOAD_LOCK:
        if date_str in _DOWNLOAD_IN_PROGRESS:
            # Another thread is already handling this date – bail out.
            return
        _DOWNLOAD_IN_PROGRESS.add(date_str)

    try:
        db_service.save_to_db(date_str)
        # Invalidate any stale cache entries for this date.
        cache.delete(f"fupan:{date_str}")
        cache.delete(f"industry:{date_str}")
        cache.delete(f"hundred_day:{date_str}")
        print(f"[fupan] background download completed for {date_str}")
    except Exception as exc:
        print(f"[fupan] background download failed for {date_str}: {exc}")
    finally:
        with _DOWNLOAD_LOCK:
            _DOWNLOAD_IN_PROGRESS.discard(date_str)


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@api_view(["POST"])
def upload(request):
    """POST /api/upload/ – Upload a CSV file to the stock_data directory.

    Accepts a single file in the ``file`` field of a multipart/form-data
    request.  Only ``.csv`` files are accepted.  The file is saved as-is
    under ``settings.STOCK_DATA_DIR`` using its original filename.

    On success, returns::

        {"filename": "<saved filename>", "path": "<absolute path>", "size": <bytes>}

    On error (no file / wrong type / write failure), returns a 4xx/5xx
    response with an ``error`` key.

    Special case – ``沪深京A股.csv``:
        When this filename is uploaded it replaces the baostock-sourced
        industry classification used by ``save_to_db()``.  All analysis
        cache entries are cleared so the next query picks up the new data.
    """
    file_obj = request.FILES.get("file")
    if not file_obj:
        return Response({"error": "No file provided. Use field name 'file'."}, status=400)

    if not file_obj.name.endswith(".csv"):
        return Response(
            {"error": f"Only .csv files are accepted, got: {file_obj.name}"},
            status=400,
        )

    dest_path = os.path.join(settings.STOCK_DATA_DIR, file_obj.name)

    try:
        with open(dest_path, "wb") as f:
            for chunk in file_obj.chunks():
                f.write(chunk)
    except OSError as exc:
        return Response({"error": f"Failed to save file: {exc}"}, status=500)

    # When the industry reference file is (re-)uploaded, flush all analysis
    # caches so subsequent requests re-run the merge with fresh data.
    if file_obj.name == "沪深京A股.csv":
        cache.clear()

    return Response(
        {
            "filename": file_obj.name,
            "path": dest_path,
            "size": file_obj.size,
        },
        status=201,
    )



# ---------------------------------------------------------------------------
# Save stock industry JSON
# ---------------------------------------------------------------------------

@api_view(["POST"])
def save_stock_industry_json(request):
    """POST /api/save-stock-industry-json/ – Persist a JSON body to stock_industry.json.

    Accepts any valid JSON object or array in the request body and writes it
    to ``stock_industry.json`` inside ``settings.STOCK_DATA_DIR``, overwriting
    any previous content.  The analysis cache is cleared so subsequent queries
    pick up the updated data.

    Returns::

        {"path": "<absolute path>", "bytes": <written bytes>}
    """
    import json as _json

    body = request.data
    if not isinstance(body, (dict, list)):
        return Response(
            {"error": "Request body must be a JSON object or array."},
            status=400,
        )

    dest_path = os.path.join(settings.STOCK_DATA_DIR, "stock_industry.json")

    try:
        payload = _json.dumps(body, ensure_ascii=False, indent=2)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(payload)
    except OSError as exc:
        return Response({"error": f"Failed to write file: {exc}"}, status=500)

    cache.clear()

    return Response(
        {"path": dest_path, "bytes": len(payload.encode())},
        status=201,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@api_view(["GET"])
def health(request):
    """GET /api/health/ – Simple liveness probe."""
    return Response({"status": "ok"})


# ---------------------------------------------------------------------------
# Page initialisation
# ---------------------------------------------------------------------------

@api_view(["POST"])
def init(request):
    """POST /api/init/ – Resolve the initial display date for the frontend.

    Decision matrix:
      - Today is a trading day AND data exists in DB  → return today.
      - Today is a trading day BUT data is absent     → start background
            download, return the most recent available date with a hint.
      - Today is a weekend / holiday                  → return most recent
            available date with an appropriate hint.
      - DB is completely empty                        → return today's date
            with a "data preparing" hint.

    Returns:
        JSON with keys: date, hint, is_today, available_dates.
    """
    today = data_service.get_current_date_str()
    is_hol, hol_reason = data_service.is_weekend_or_holiday(today)
    available = db_service.get_available_dates()

    hint = ""
    is_today = False

    if not is_hol:
        # Today is a trading day.
        now = datetime.now()
        if now.hour >= 18:
            if db_service.has_date(today):
                date = today
                is_today = True
                hint = "Today's data loaded."
            else:
                # Trigger a one-shot background download (deduplicated by lock).
                with _DOWNLOAD_LOCK:
                    already = today in _DOWNLOAD_IN_PROGRESS
                if not already:
                    t = threading.Thread(
                        target=_do_download_and_save,
                        args=(today,),
                        daemon=True,
                    )
                    t.start()

                date = today
                is_today = True
                hint = "Preparing…"
        else:
            date = today
            hint = "Data updates at 18:00 on trading days"
    else:
        # Today is a weekend or public holiday.
        if available:
            date = available[0]
            hint = (
                f"{hol_reason}. Showing the most recent trading day {date}. "
                f"Data updates at 18:00 on trading days."
            )
        else:
            date = today
            hint = "No data yet. Data updates at 18:00 on trading days."

    return Response(
        {
            "date": date,
            "hint": hint,
            "is_today": is_today,
            "available_dates": available,
        }
    )


# ---------------------------------------------------------------------------
# Daily review table
# ---------------------------------------------------------------------------

@api_view(["GET"])
def fupan(request):
    """GET /api/fupan/?date=YYYY-MM-DD – Daily review (large movers).

    Returns stocks whose price change is ≥ 8 % (or ≤ -8 %) and whose
    trading volume exceeds 800 million CNY, split by exchange and direction.
    Results are cached for 12 hours per date.
    """
    today = data_service.get_current_date_str()
    date_str = request.query_params.get("date", today)
    now = datetime.now()
    if now.hour < 18 and date_str == today:
        hint = "No data yet. Data updates at 18:00 on trading days."
        return Response(
            {"hint": hint}, status=404
        )

    cache_key = f"fupan:{date_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    try:
        data = analysis_service.get_fupan_data(date_str)
        cache.set(cache_key, data, CACHE_TTL)
        return Response(data)
    except FileNotFoundError as exc:
        return Response(
            {"error": str(exc), "hint": "No data for this date."}, status=404
        )
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Sector / industry analysis
# ---------------------------------------------------------------------------

@api_view(["GET"])
def industry(request):
    """GET /api/industry/?date=YYYY-MM-DD – Sector analysis.

    Returns two sector summaries (stocks with >5 % gain, and the top-10 %
    of all stocks by gain) plus matplotlib bar charts encoded as base-64 PNG.
    Results are cached for 12 hours per date.
    """
    today = data_service.get_current_date_str()
    date_str = request.query_params.get("date", today)
    now = datetime.now()
    if now.hour < 18 and date_str == today:
        hint = "No data yet. Data updates at 18:00 on trading days."
        return Response(
            {"hint": hint}, status=404
        )

    cache_key = f"industry:{date_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    try:
        data = analysis_service.get_industry_analysis(date_str)
        cache.set(cache_key, data, CACHE_TTL)
        return Response(data)
    except FileNotFoundError as exc:
        return Response(
            {"error": str(exc), "hint": "No data for this date."}, status=404
        )
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# 100-day new high / new low analysis
# ---------------------------------------------------------------------------

@api_view(["GET"])
def hundred_day(request):
    """GET /api/hundred-day/?date=YYYY-MM-DD – 100-day new high / low.

    For the given trading date, returns:
      - new_high_sectors: top sectors by number of 100-day high stocks
      - new_low_sectors:  top sectors by number of 100-day low stocks
      - ratio_chart_b64:  bar chart PNG (base-64) of the ratio over time
      - high_count / low_count / total_stocks: summary figures

    Results are cached for 12 hours per date.
    """
    today = data_service.get_current_date_str()
    date_str = request.query_params.get("date", today)
    now = datetime.now()
    if now.hour < 18 and date_str == today:
        hint = "No data yet. Data updates at 18:00 on trading days."
        return Response(
            {"hint": hint}, status=404
        )
    cache_key = f"hundred_day:{date_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    try:
        data = hundred_day_service.get_hundred_day_analysis(date_str)
        cache.set(cache_key, data, CACHE_TTL)
        return Response(data)
    except FileNotFoundError as exc:
        return Response(
            {"error": str(exc), "hint": "No data for this date."}, status=404
        )
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Available dates
# ---------------------------------------------------------------------------

@api_view(["GET"])
def available_dates(request):
    """GET /api/dates/ – List trading dates that have data in the DB.

    Returns a JSON array of date strings sorted in descending order.
    """
    return Response(db_service.get_available_dates())
