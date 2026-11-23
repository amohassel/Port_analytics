"""Step 3: download daily trade data for the tracked ports and keep a local copy.

First run: pulls the full history (2019 onward) for every port in ports.csv.
Later runs: re-pulls only the last REFRESH_WEEKS weeks, because PortWatch's
figures are preliminary and get revised, then replaces that window in the CSV.
A port that is new to ports.csv gets its full history.
"""

from __future__ import annotations

import logging

import pandas as pd

from portwatch import client, config

logger = logging.getLogger(__name__)

KEY = ["portid", "date"]
DROP_COLS = ["ObjectId", "GlobalID", "year", "month", "day"]  # ArcGIS bookkeeping / redundant


def _in_clause(values: list[str]) -> str:
    quoted = ",".join(f"'{v}'" for v in values)
    return f"({quoted})"


def fetch_daily(port_ids: list[str], since: str | None = None, session=None) -> pd.DataFrame:
    """Daily rows for `port_ids`, optionally only from `since` (YYYY-MM-DD) onward.

    If the server rejects the date filter, fall back to the full history and
    filter locally. Slower, but the run still succeeds.
    """
    where = f"portid IN {_in_clause(port_ids)}"
    if since:
        try:
            df = client.query_layer(
                client.DAILY_TRADE_LAYER,
                where=f"{where} AND date >= TIMESTAMP '{since} 00:00:00'",
                session=session,
            )
        except client.PortWatchError as err:
            logger.warning("Date filter rejected (%s); fetching full history instead.", err)
            df = client.query_layer(client.DAILY_TRADE_LAYER, where=where, session=session)
    else:
        df = client.query_layer(client.DAILY_TRADE_LAYER, where=where, session=session)

    return clean_daily(df, since=since)


def clean_daily(df: pd.DataFrame, since: str | None = None) -> pd.DataFrame:
    """Convert dates, drop bookkeeping columns, de-duplicate, sort."""
    if df.empty:
        return df
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    df["date"] = client.epoch_ms_to_date(df["date"])
    if since:
        df = df[df["date"] >= pd.Timestamp(since)]
    return (
        df.drop_duplicates(subset=KEY, keep="last")
        .sort_values(KEY)
        .reset_index(drop=True)
    )


def merge_refresh(existing: pd.DataFrame, fresh: pd.DataFrame, since: str) -> pd.DataFrame:
    """Replace rows on/after `since` for the refreshed ports with `fresh`.

    Rows before `since` are kept as they are. If PortWatch dropped a row from the
    refresh window, it is dropped here too, so the local copy mirrors the source.
    """
    refreshed_ports = fresh["portid"].unique()
    stale = existing["portid"].isin(refreshed_ports) & (existing["date"] >= pd.Timestamp(since))
    out = pd.concat([existing[~stale], fresh], ignore_index=True)
    return out.drop_duplicates(subset=KEY, keep="last").sort_values(KEY).reset_index(drop=True)


def load_daily() -> pd.DataFrame:
    return pd.read_csv(config.DAILY_CSV, parse_dates=["date"])


def update_daily(ports: pd.DataFrame, session=None) -> pd.DataFrame:
    """Bring data/daily_trade.csv up to date for every port in `ports`."""
    port_ids = ports["portid"].tolist()

    if not config.DAILY_CSV.exists():
        logger.info("No local data yet; fetching full history for %d ports.", len(port_ids))
        daily = fetch_daily(port_ids, session=session)
    else:
        daily = load_daily()
        new_ports = sorted(set(port_ids) - set(daily["portid"]))
        known_ports = [p for p in port_ids if p not in new_ports]

        if new_ports:
            logger.info("New ports, fetching full history: %s", new_ports)
            daily = pd.concat([daily, fetch_daily(new_ports, session=session)], ignore_index=True)

        since = (daily["date"].max() - pd.Timedelta(weeks=config.REFRESH_WEEKS)).strftime("%Y-%m-%d")
        logger.info("Refreshing %d ports from %s.", len(known_ports), since)
        fresh = fetch_daily(known_ports, since=since, session=session)
        daily = merge_refresh(daily, fresh, since)

        # Ports removed from ports.csv are dropped from the data as well.
        daily = daily[daily["portid"].isin(port_ids)].reset_index(drop=True)

    if daily.empty:
        raise client.PortWatchError("No daily rows returned; not overwriting local data.")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    daily.to_csv(config.DAILY_CSV, index=False)
    logger.info(
        "Saved %d rows (%s to %s) to %s",
        len(daily), daily["date"].min().date(), daily["date"].max().date(), config.DAILY_CSV,
    )
    return daily


if __name__ == "__main__":
    from portwatch import ports as ports_mod

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    daily = update_daily(ports_mod.build_port_list())
    summary = daily.groupby("portname").agg(
        first=("date", "min"), last=("date", "max"), days=("date", "size"),
        port_calls=("portcalls", "sum"),
    )
    print(summary.sort_values("port_calls", ascending=False).to_string())
