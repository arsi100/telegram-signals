import time, logging, os, requests
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

API_URL = "https://api.bybit.com/v5/market/kline"

DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)


def fetch_kline_extended(symbol: str, interval: str = "15", days: int = 90, category: str = "linear") -> pd.DataFrame:
    """Fetch up to `days` worth of klines, handling the 2000-candle limit.

    Results are cached to data/{symbol}_{interval}m.csv so subsequent calls load from disk.
    """
    cache_file = DATA_DIR / f"{symbol}_{interval}m.csv"
    if cache_file.exists():
        df = pd.read_csv(cache_file, parse_dates=["ts"])
        if not df.empty and (df["ts"].max() - df["ts"].min()).days >= days - 1:
            return df
    logger.info("Fetching extended klines for %s %sm", symbol, interval)
    end_ms = int(time.time() * 1000)
    cutoff_ms = end_ms - days * 24 * 60 * 60 * 1000
    all_rows = []
    while True:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000,
            "category": category,
            "end": end_ms,
        }
        resp = requests.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0 or not data["result"].get("list"):
            logger.error("API error fetching klines: %s", data.get("retMsg"))
            break
        batch = data["result"]["list"]
        # reverse order so ascending
        batch = sorted(batch, key=lambda x: int(x[0]))
        all_rows.extend(batch)
        earliest = int(batch[0][0])
        if earliest <= cutoff_ms or len(batch) < 1000:
            break
        end_ms = earliest - 1
        time.sleep(0.25)  # avoid rate limit
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows, columns=["ts","open","high","low","close","vol","turn"])
    df[["open","high","low","close","vol","turn"]] = df[["open","high","low","close","vol","turn"]].astype(float)
    df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms", utc=True)
    df.sort_values("ts", inplace=True)
    df.to_csv(cache_file, index=False)
    return df 