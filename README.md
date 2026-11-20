# Port analytics

Weekly monitoring of activity at the busiest US ports, built on
[IMF PortWatch](https://portwatch.imf.org) daily port-call and trade-volume estimates.

## Status

Work in progress, built one module at a time:

| Step | Module | Status |
|---|---|---|
| 1 | `portwatch/client.py` — PortWatch API access with paging and retries | done |
| 2 | `portwatch/ports.py` — select the 15 busiest US ports | done |
| 3 | `portwatch/fetch.py` — download and update daily trade data | next |
| 4 | `portwatch/transform.py` — weekly totals, 2019 index, year-over-year change | |
| 5 | `portwatch/checks.py` — data checks | |
| 6 | `portwatch/plot.py` — Plotly charts and map | |
| 7 | `portwatch/pipeline.py` + GitHub Actions weekly run | |

## Setup

```bash
conda create -n ports python=3.12 -y
conda activate ports
pip install -r us_port_activity/requirements.txt

cd us_port_activity
python -m pytest -q          # offline tests
python -m portwatch.ports    # build data/ports.csv
```

## Layout

```
us_port_activity/
  portwatch/      pipeline package (settings in config.py)
  tests/          offline tests (no network needed)
  data/           pipeline outputs (ports.csv, ...)
```

`port_trade_network.csv` (global port-to-port network, ~489 MB) is kept locally
and excluded from git.

## Data and terms

Data: IMF PortWatch (IMF and University of Oxford). Estimates are preliminary and
derived from AIS ship-tracking data. Free for non-commercial use; commercial reuse
needs IMF permission. Credit "IMF PortWatch" when publishing charts.
