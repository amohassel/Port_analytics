"""Offline tests for the PortWatch client, using a fake HTTP session."""

import pandas as pd
import pytest

from portwatch import client


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    """Serves pre-baked pages and records the params of each call."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(params)
        return FakeResponse(self.pages.pop(0))


def page(ids, more):
    return {"features": [{"attributes": {"id": i}} for i in ids],
            "exceededTransferLimit": more}


def test_paginates_until_limit_flag_clears():
    s = FakeSession([page([1, 2], True), page([3], False)])
    df = client.query_layer("X", session=s)
    assert df["id"].tolist() == [1, 2, 3]
    assert [c["resultOffset"] for c in s.calls] == [0, client.PAGE_SIZE]


def test_error_payload_raises():
    s = FakeSession([{"error": {"code": 400, "message": "bad where"}}])
    with pytest.raises(client.PortWatchError):
        client.query_layer("X", session=s)


def test_list_out_fields_are_joined():
    s = FakeSession([page([1], False)])
    client.query_layer("X", out_fields=["a", "b"], session=s)
    assert s.calls[0]["outFields"] == "a,b"


def test_epoch_ms_to_date():
    ms = pd.Series([1704067200000])  # 2024-01-01T00:00:00Z
    assert client.epoch_ms_to_date(ms).iloc[0] == pd.Timestamp("2024-01-01")
