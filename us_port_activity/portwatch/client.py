"""Thin client for the IMF PortWatch ArcGIS REST API.

PortWatch publishes its tables as ArcGIS FeatureServer layers. Every layer
supports the same `/query` endpoint, returns at most ~1,000 rows per call,
and signals "there is more" with `exceededTransferLimit: true`.

This module knows nothing about ports or trade. It only turns
"layer name + SQL-like filter" into a pandas DataFrame, handling paging,
retries and ArcGIS's habit of returning errors with HTTP 200.
"""

from __future__ import annotations

import logging

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"

# Layer names as published by PortWatch.
PORTS_LAYER = "PortWatch_ports_database"
DAILY_TRADE_LAYER = "Daily_Trade_Data"

PAGE_SIZE = 1000  # server-side maximum per request


class PortWatchError(RuntimeError):
    """Raised when the API returns an error payload or malformed data."""


def make_session(retries: int = 3, backoff: float = 1.0) -> requests.Session:
    """Session that retries transient failures (429/5xx) with backoff."""
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def query_layer(
    layer: str,
    where: str = "1=1",
    out_fields: str | list[str] = "*",
    order_by: str = "ObjectId",
    session: requests.Session | None = None,
    timeout: int = 60,
    max_pages: int = 500,
) -> pd.DataFrame:
    """Fetch every row of a PortWatch layer that matches `where`.

    Parameters
    ----------
    layer : FeatureServer layer name, e.g. ``DAILY_TRADE_LAYER``.
    where : ArcGIS SQL filter, e.g. ``"ISO3 = 'USA'"``.
    out_fields : columns to return; ``"*"`` for all.
    order_by : a stable sort key so pages don't overlap or skip rows.
    max_pages : safety stop so a bad filter can't loop forever.

    Returns
    -------
    DataFrame with one row per feature (attributes only, no geometry).
    """
    session = session or make_session()
    if isinstance(out_fields, list):
        out_fields = ",".join(out_fields)

    url = f"{BASE_URL}/{layer}/FeatureServer/0/query"
    rows: list[dict] = []

    for page in range(max_pages):
        params = {
            "where": where,
            "outFields": out_fields,
            "orderByFields": order_by,
            "resultOffset": page * PAGE_SIZE,
            "resultRecordCount": PAGE_SIZE,
            "returnGeometry": "false",
            "f": "json",
        }
        resp = session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()

        # ArcGIS reports errors in the body with HTTP 200.
        if "error" in payload:
            raise PortWatchError(f"{layer}: {payload['error']}")

        features = payload.get("features", [])
        rows.extend(f["attributes"] for f in features)
        logger.debug("%s page %d: %d rows", layer, page, len(features))

        if not payload.get("exceededTransferLimit") or not features:
            break
    else:
        raise PortWatchError(f"{layer}: hit max_pages={max_pages}; refine `where`.")

    logger.info("%s: fetched %d rows", layer, len(rows))
    return pd.DataFrame(rows)


def epoch_ms_to_date(series: pd.Series) -> pd.Series:
    """ArcGIS returns dates as epoch milliseconds (UTC); convert to dates."""
    return pd.to_datetime(series, unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
