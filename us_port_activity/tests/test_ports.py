"""Tests for port selection (no network)."""

import pandas as pd
import pytest

from portwatch import ports


def sample_ports():
    return pd.DataFrame({
        "portid": ["p1", "p2", "p3"],
        "portname": ["A", "B", "C"],
        "ISO3": ["USA"] * 3,
        "lat": [1.0, 2.0, 3.0],
        "lon": [4.0, 5.0, 6.0],
        "vessel_count_total": [10, 30, 20],
    })


def test_top_n_sorted_and_ranked():
    top = ports.select_top_ports(sample_ports(), n=2)
    assert top["portid"].tolist() == ["p2", "p3"]
    assert top["rank"].tolist() == [1, 2]


def test_missing_rank_column_raises():
    with pytest.raises(KeyError):
        ports.select_top_ports(sample_ports(), rank_by="nope")


def test_duplicate_ids_raise():
    df = pd.concat([sample_ports(), sample_ports().iloc[[0]]])
    with pytest.raises(ValueError):
        ports.select_top_ports(df)
