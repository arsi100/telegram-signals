import sys, logging
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.bybit_api import fetch_kline_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COINS = [
    "SOLUSDT", "BTCUSDT", "ETHUSDT", "ADAUSDT", "LINKUSDT", "XRPUSDT",
    "AVAXUSDT", "DOTUSDT", "ATOMUSDT", "HBARUSDT", "CROUSDT", "SUIUSDT"
]  # removed XMR and SEI

INTERVAL = "30"
LOOKBACK_DAYS = 90
TP1 = 0.5  # scale-out trigger
TRAIL_GAP = 0.25  # trailing stop gap after TP1
SL = -1.5
RSI_MIN, RSI_MAX = 45, 60
CAPITAL = 100_000
MARGIN_PER_TRADE = 0.10
MAX_CONCURRENT = 2

OUT = Path("analysis_results/refined_v2"); OUT.mkdir(parents=True, exist_ok=True)

def fetch(symbol):
    kl = fetch_kline_data(symbol, interval=INTERVAL, limit=2000, category="linear")
    if not kl:
        return pd.DataFrame()
    df = pd.DataFrame(kl, columns=["ts","open","high","low","close","vol","turn"])
    df[["open","high","low","close","vol"]] = df[["open","high","low","close","vol"]].astype(float)
    df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms", utc=True)
    df.sort_values("ts", inplace=True)
    cutoff = df["ts"].max()-pd.Timedelta(days=LOOKBACK_DAYS)
    return df[df["ts"]>=cutoff].reset_index(drop=True)

def add_ind(df):
    df["ema10"] = df["close"].ewm(span=10).mean()
    df["price_vs_ema10"] = (df["close"]-df["ema10"])/df["ema10"]*100
    delta=df["close"].diff(); gain=np.where(delta>0,delta,0); loss=np.where(delta<0,-delta,0)
    df["rsi14"] = 100-100/(1+pd.Series(gain).rolling(14).mean()/pd.Series(loss).rolling(14).mean())
    df["rsi_slope"] = df["rsi14"].diff()
    df["vol_z"] = (df["vol"]-df["vol"].rolling(20).mean())/df["vol"].rolling(20).std()
    df["range_pct"]=(df["high"]-df["low"])/df["low"]*100
    return df

def simulate(symbol):
    df=fetch(symbol)
    if df.empty:
        return None
    df=add_ind(df)
    sig_idx=df.index[(df["range_pct"]>0.5)&(df["rsi14"].between(RSI_MIN,RSI_MAX))&(df["rsi_slope"]>=0)&(df["vol_z"]>0)&(df["price_vs_ema10"].between(-0.3,0.3))]
    positions=[]; trades=[]
    for idx,row in df.iterrows():
        # manage existing
        still=[]
        for pos in positions:
            high=row["high"]; low=row["low"]
            if not pos["scale"] and (high-pos["entry"])/pos["entry"]*100>=TP1:
                pos["scale"]=True; pos["peak"]=high
                pos["pnl_realized"]=TP1*0.5  # 50% position closed
            if pos["scale"]:
                if high>pos["peak"]: pos["peak"]=high
                # trailing stop
                if (pos["peak"]-low)/pos["peak"]*100>=TRAIL_GAP:
                    remaining_pnl=(low-pos["entry"])/pos["entry"]*100
                    trades.append({"entry_ts":pos["ts"],"exit_ts":row["ts"],"pnl_pct":pos["pnl_realized"]+remaining_pnl*0.5})
                    continue
            # hard stop
            if (low-pos["entry"])/pos["entry"]*100<=SL:
                total_pnl=pos.get("pnl_realized",0)+(SL*0.5 if pos.get("scale") else SL)
                trades.append({"entry_ts":pos["ts"],"exit_ts":row["ts"],"pnl_pct":total_pnl})
            else:
                still.append(pos)
        positions=still
        # new entry
        if idx in sig_idx and len(positions)<MAX_CONCURRENT:
            positions.append({"entry":row["open"],"ts":row["ts"],"scale":False,"peak":row["high"]})
    # close remaining at final close
    final_close=df.iloc[-1]["close"]; final_ts=df.iloc[-1]["ts"]
    for pos in positions:
        remain_pnl=(final_close-pos["entry"])/pos["entry"]*100
        trades.append({"entry_ts":pos["ts"],"exit_ts":final_ts,"pnl_pct":pos.get("pnl_realized",0)+remain_pnl*(0.5 if pos.get("scale") else 1)})
    tr=pd.DataFrame(trades)
    tr.to_csv(OUT/f"{symbol}_trades.csv",index=False)
    return {"symbol":symbol,"trades":len(tr),"wins":(tr["pnl_pct"]>0).sum(),"losses":(tr["pnl_pct"]<0).sum(),"avg_pct":tr["pnl_pct"].mean(),"total_pct":tr["pnl_pct"].sum()}

def main():
    summ=[]
    for sym in COINS:
        logger.info("Sim %s", sym); s=simulate(sym); summ.append(s)
    pd.DataFrame(summ).to_csv(OUT/"summary.csv",index=False); print(pd.DataFrame(summ))

if __name__=="__main__":
    main() 