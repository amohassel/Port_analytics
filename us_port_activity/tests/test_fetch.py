"""Tests for the daily fetch/merge logic (no network)."""

import pandas as pd

from portwatch import client, config, fetch


def ms(date):
    return int(pd.Timestamp(date).timestamp() * 1000)


def raw(rows):
    """Rows of (portid, date, portcalls) shaped like the API's attributes."""
    return pd.DataFrame(
        [{"portid": p, "date": ms(d), "portcalls": c, "ObjectId": i}
         for i, (p, d, c) in enumerate(rows)]
    )


def test_clean_daily_converts_and_dedupes():
    df = fetch.clean_daily(raw([("p1", "2024-01-02", 1), ("p1", "2024-01-01", 2), ("p1", "2024-01-02", 3)]))
    assert "ObjectId" not in df.columns
    assert df["date"].tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert df["portcalls"].tolist() == [2, 3]  # later duplicate wins


def test_merge_refresh_replaces_window_only():
    existing = fetch.clean_daily(raw([("p1", "2024-01-01", 1), ("p1", "2024-02-01", 1), ("p2", "2024-02-01", 9)]))
    fresh = fetch.clean_daily(raw([("p1", "2024-02-01", 5), ("p1", "2024-02-02", 6)]))
    out = fetch.merge_refresh(existing, fresh, since="2024-01-15")
    p1 = out[out.portid == "p1"]
    assert p1["portcalls"].tolist() == [1, 5, 6]              # old row kept, window replaced
    assert out[out.portid == "p2"]["portcalls"].tolist() == [9]  # other port untouched


def test_date_filter_fallback(monkeypatch):
    calls = []

    def fake_query(layer, where, session=None):
        calls.append(where)
        if "TIMESTAMP" in where:
            raise client.PortWatchError("bad where")
        return raw([("p1", "2023-12-01", 1), ("p1", "2024-02-01", 2)])

    monkeypatch.setattr(client, "query_layer", fake_query)
    df = fetch.fetch_daily(["p1"], since="2024-01-01")
    assert len(calls) == 2                       # retried without date filter
    assert df["portcalls"].tolist() == [2]       # filtered locally


def test_update_daily_incremental(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DAILY_CSV", tmp_path / "daily.csv")
    monkeypatch.setattr(config, "REFRESH_WEEKS", 1)
    ports = pd.DataFrame({"portid": ["p1"]})

    history = raw([("p1", "2024-01-01", 1), ("p1", "2024-03-01", 1)])
    monkeypatch.setattr(client, "query_layer", lambda layer, where, session=None: history)
    fetch.update_daily(ports)                            # first run: full history

    seen = []
    def fake_query(layer, where, session=None):
        seen.append(where)
        return raw([("p1", "2024-03-01", 7), ("p1", "2024-03-02", 8)])
    monkeypatch.setattr(client, "query_layer", fake_query)
    out = fetch.update_daily(ports)                      # second run: refresh window

    assert "TIMESTAMP '2024-02-23" in seen[0]
    assert out["portcalls"].tolist() == [1, 7, 8]
