"""Settings shared across the pipeline. Change things here, not in the modules."""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"

COUNTRY_ISO3 = "USA"
N_PORTS = 15                      # how many of the busiest ports to track
RANK_BY = "vessel_count_total"    # ports-table column used to rank "busiest"
START_DATE = "2019-01-01"         # PortWatch daily data begins here

PORTS_CSV = DATA_DIR / "ports.csv"

DAILY_CSV = DATA_DIR / "daily_trade.csv"
REFRESH_WEEKS = 8                 # PortWatch revises recent weeks; re-pull this window each run
