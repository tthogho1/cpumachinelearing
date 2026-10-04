"""Download economic indicator time series (no API key required) and save as CSV.

Sources:
  - World Bank API  (annual, any country)   https://api.worldbank.org/v2/
  - FRED graph CSV  (monthly/quarterly, US + some intl series)  https://fred.stlouisfed.org/

Usage:
  python fetch_economic_data.py                 # default set -> data/
  python fetch_economic_data.py --country JPN   # World Bank country (ISO3)
"""

import argparse
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

# World Bank indicator code -> column name
WORLD_BANK_INDICATORS = {
    "FP.CPI.TOTL.ZG": "inflation_cpi_pct",
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
    "NY.GDP.PCAP.CD": "gdp_per_capita_usd",
    "SL.UEM.TOTL.ZS": "unemployment_pct",
    "SP.POP.TOTL": "population",
    "NE.TRD.GNFS.ZS": "trade_pct_gdp",
}

# FRED series id -> column name
FRED_SERIES = {
    "CPIAUCSL": "us_cpi",                 # monthly, index
    "UNRATE": "us_unemployment_pct",      # monthly
    "FEDFUNDS": "us_fed_funds_pct",       # monthly
    "INDPRO": "us_industrial_production", # monthly, index
    "DGS10": "us_10y_treasury_pct",       # daily
    "JPNCPIALLMINMEI": "jp_cpi",          # monthly, index (OECD via FRED; stopped updating 2021-06)
}

TIMEOUT = 30


def fetch_world_bank(country: str, indicator: str) -> pd.Series:
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
    resp = requests.get(url, params={"format": "json", "per_page": 20000}, timeout=TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    # Response is [metadata, rows]; rows is None when the indicator has no data.
    if len(payload) < 2 or not payload[1]:
        raise ValueError(f"No data for {country}/{indicator}: {payload[0]}")
    rows = payload[1]
    s = pd.Series(
        {int(r["date"]): r["value"] for r in rows},
        name=WORLD_BANK_INDICATORS.get(indicator, indicator),
        dtype="float64",
    )
    return s.sort_index()


def fetch_fred(series_id: str) -> pd.Series:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    resp = requests.get(url, params={"id": series_id}, timeout=TIMEOUT)
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text), na_values=".")
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["value"].rename(FRED_SERIES.get(series_id, series_id))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--country", default="JPN", help="ISO3 country code for World Bank (default: JPN)")
    parser.add_argument("--out", default="data", help="Output directory (default: data)")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # World Bank: one annual table, one column per indicator
    wb_cols = []
    for code in WORLD_BANK_INDICATORS:
        try:
            wb_cols.append(fetch_world_bank(args.country, code))
            print(f"  World Bank {code}: ok")
        except Exception as e:
            print(f"  World Bank {code}: FAILED ({e})")
    if wb_cols:
        wb = pd.concat(wb_cols, axis=1).dropna(how="all")
        wb.index.name = "year"
        path = out / f"worldbank_{args.country.lower()}_annual.csv"
        wb.to_csv(path)
        print(f"Saved {path}  ({len(wb)} rows, {wb.index.min()}-{wb.index.max()})")

    # FRED: each series saved separately (frequencies differ), plus a monthly merged table
    monthly = []
    for sid in FRED_SERIES:
        try:
            s = fetch_fred(sid)
        except Exception as e:
            print(f"  FRED {sid}: FAILED ({e})")
            continue
        s.to_frame().to_csv(out / f"fred_{sid.lower()}.csv")
        print(f"  FRED {sid}: {len(s)} rows, {s.index.min().date()} - {s.index.max().date()}")
        # Resample to month-start so daily and monthly series line up
        monthly.append(s.resample("MS").mean())
    if monthly:
        merged = pd.concat(monthly, axis=1, sort=True).dropna(how="all")
        merged.index.name = "date"
        path = out / "fred_monthly_merged.csv"
        merged.to_csv(path)
        print(f"Saved {path}  ({len(merged)} rows)")


if __name__ == "__main__":
    main()
