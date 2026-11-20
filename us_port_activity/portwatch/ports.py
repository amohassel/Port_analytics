"""Step 2: choose which ports the pipeline tracks.

Pulls the PortWatch ports table for one country, keeps the N busiest,
and saves them to data/ports.csv. Later steps read that file, so the
port list stays fixed between weekly runs unless you rebuild it.
"""

from __future__ import annotations

import logging

import pandas as pd

from portwatch import client, config

logger = logging.getLogger(__name__)

# Columns worth keeping for later steps (map position, labels, context).
KEEP_COLS = [
    "portid", "portname", "fullname", "ISO3", "lat", "lon",
    "vessel_count_total", "vessel_count_container", "vessel_count_dry_bulk",
    "vessel_count_general_cargo", "vessel_count_RoRo", "vessel_count_tanker",
    "industry_top1", "share_country_maritime_import", "share_country_maritime_export",
]


def fetch_country_ports(iso3: str = config.COUNTRY_ISO3, session=None) -> pd.DataFrame:
    """All PortWatch ports for one country."""
    return client.query_layer(client.PORTS_LAYER, where=f"ISO3 = '{iso3}'", session=session)


def select_top_ports(
    ports: pd.DataFrame, n: int = config.N_PORTS, rank_by: str = config.RANK_BY
) -> pd.DataFrame:
    """Keep the `n` ports with the highest `rank_by`, busiest first.

    Pure function (no I/O) so it's easy to test and reuse.
    """
    if rank_by not in ports.columns:
        raise KeyError(f"'{rank_by}' not in ports table; columns: {list(ports.columns)}")
    if ports["portid"].duplicated().any():
        raise ValueError("Duplicate portid values in ports table.")

    cols = [c for c in KEEP_COLS if c in ports.columns]
    missing = sorted(set(KEEP_COLS) - set(cols))
    if missing:
        logger.warning("Ports table lacks expected columns: %s", missing)

    top = (
        ports.sort_values(rank_by, ascending=False)
        .head(n)[cols]
        .reset_index(drop=True)
    )
    top.insert(0, "rank", range(1, len(top) + 1))
    return top


def build_port_list(force: bool = False, session=None) -> pd.DataFrame:
    """Load data/ports.csv, or create it from the API if missing / `force`."""
    if config.PORTS_CSV.exists() and not force:
        logger.info("Using existing %s", config.PORTS_CSV)
        return pd.read_csv(config.PORTS_CSV)

    top = select_top_ports(fetch_country_ports(session=session))
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    top.to_csv(config.PORTS_CSV, index=False)
    logger.info("Saved %d ports to %s", len(top), config.PORTS_CSV)
    return top


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Build the list of tracked ports.")
    parser.add_argument("--force", action="store_true", help="re-download even if ports.csv exists")
    args = parser.parse_args()

    ports = build_port_list(force=args.force)
    print(ports[["rank", "portid", "portname", config.RANK_BY]].to_string(index=False))
