"""US RSI(2) 평균회귀 백테스트 (래리 코너스 규칙, yfinance 일봉).

검증 전용. 통과했을 때만 라이브 인프라(broker_us 등)를 별도로 구축한다.
데이터는 yfinance로 받는다 (스크리닝에 KIS를 쓰지 않는다). 판정은 기존
backtest_multi와 동일하게 거래당 수익률·MDD·승률로 하고, 누적 수치는 전액
재투자 복리 아티팩트라 참고만 한다.

규칙:
- 필터: 종가 > SMA200 (장기 상승추세에서만)
- 진입: RSI(2) < 5  -> 익일 시가 매수
- 청산(우선순위): (1) 당일 저가가 진입가 -7% 이하면 손절가로 청산
                   (2) 종가 > SMA5 -> 익일 시가 청산
                   (3) 진입 후 10거래일 경과 -> 익일 시가 강제 청산

사용법:
    python backtest_us_rsi2.py --split          # 전체/하락/회복/최근 4구간 (권장)
    python backtest_us_rsi2.py                  # 전체 기간만
    python backtest_us_rsi2.py --limit 20       # 앞 20종목만 (빠른 점검)
"""
import argparse
import time

import numpy as np
import pandas as pd

from backtest_multi import _fmt, summarize  # 리포트 형식 재사용
from us_universe import load_us_universe

SLIPPAGE_RATE = 0.001          # 편도 슬리피지
US_ROUND_TRIP_COST = 0.002     # 미국은 거래세 없음: 수수료+슬리피지 왕복 가정 (조정 가능)
RSI_PERIOD = 2
RSI_ENTRY = 5.0
SMA_LONG = 200
SMA_SHORT = 5
MAX_HOLD_DAYS = 10
STOP_LOSS = 0.07               # -7% 손절
START = "2021-01-01"

SPLIT_WINDOWS = [
    ("전체", None, None),
    ("하락장 2022", None, "2023-01-01"),
    ("회복장 23-24", "2023-01-01", "2025-01-01"),
    ("최근 25~", "2025-01-01", None),
]


def rsi_series(close: pd.Series, period: int = RSI_PERIOD) -> np.ndarray:
    """와일더 방식 RSI. period=2면 코너스 RSI(2)."""
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = roll_up / roll_down
    return (100 - 100 / (1 + rs)).to_numpy()


def rsi2_trades(df: pd.DataFrame) -> list[dict]:
    """한 종목의 RSI(2) 거래 목록. 미래 참조 없음(신호는 t 종가, 체결은 t+1 시가)."""
    df = df.sort_index()
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)   # noqa: F841 (가독성 위해 유지)
    low = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    n = len(c)
    if n < SMA_LONG + 5:
        return []

    cs = pd.Series(c)
    sma200 = cs.rolling(SMA_LONG).mean().to_numpy()
    sma5 = cs.rolling(SMA_SHORT).mean().to_numpy()
    rsi = rsi_series(cs)

    trades: list[dict] = []
    hold_i = None          # 진입 체결 인덱스
    entry_price = 0.0
    for t in range(SMA_LONG, n - 1):
        if hold_i is None:
            # 진입 신호 (t 종가 기준) -> t+1 시가 매수
            if c[t] > sma200[t] and rsi[t] < RSI_ENTRY:
                hold_i = t + 1
                entry_price = o[t + 1] * (1 + SLIPPAGE_RATE)
            continue

        u = t
        if u < hold_i:
            continue
        stop_level = entry_price * (1 - STOP_LOSS)
        # (1) 당일 저가가 손절선 이하 -> 손절가 청산 (리스크 우선)
        if low[u] <= stop_level:
            ret = (stop_level / entry_price) * (1 - US_ROUND_TRIP_COST) - 1
            trades.append({"date": dates[u], "ret": ret, "hold": u - hold_i + 1})
            hold_i = None
            continue
        # (2) 종가 > SMA5 -> 익일 시가 청산
        if c[u] > sma5[u]:
            ret = (o[u + 1] / entry_price) * (1 - US_ROUND_TRIP_COST) - 1
            trades.append({"date": dates[u + 1], "ret": ret, "hold": u + 1 - hold_i})
            hold_i = None
            continue
        # (3) 보유 10거래일 상한 도달 -> 익일 시가 강제 청산 (hold == MAX_HOLD_DAYS)
        if u - hold_i >= MAX_HOLD_DAYS - 1:
            ret = (o[u + 1] / entry_price) * (1 - US_ROUND_TRIP_COST) - 1
            trades.append({"date": dates[u + 1], "ret": ret, "hold": u + 1 - hold_i})
            hold_i = None
            continue

    if hold_i is not None:  # 마지막 바까지 미청산분은 종가로 마감
        ret = (c[-1] / entry_price) * (1 - US_ROUND_TRIP_COST) - 1
        trades.append({"date": dates[-1], "ret": ret, "hold": n - 1 - hold_i})
    return trades


def load_prices(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.download(ticker, start=START, auto_adjust=True, progress=False)


def collect_trades(tickers: list[str]) -> pd.DataFrame:
    all_trades, failed = [], []
    for i, tk in enumerate(tickers, 1):
        try:
            df = load_prices(tk)
            if df is None or len(df) < SMA_LONG + 20:
                continue
            if isinstance(df.columns, pd.MultiIndex):   # 단일 티커도 가끔 멀티인덱스로 옴
                df.columns = df.columns.get_level_values(0)
            all_trades.extend(rsi2_trades(df))
        except Exception as exc:
            failed.append(f"{tk}({exc})")
        time.sleep(0.3)
        if i % 20 == 0:
            print(f"  ... 로드/계산 {i}/{len(tickers)}")
    if failed:
        print(f"[로드 실패 {len(failed)}종목] {', '.join(failed[:10])}{' ...' if len(failed) > 10 else ''}")
    return pd.DataFrame(all_trades)


def report_window(label: str, trades: pd.DataFrame, start, end) -> None:
    print(f"\n===== {label} ({start or '처음'} ~ {end or '현재'}) =====")
    r = summarize("rsi2", None, trades, start, end)
    print("  거래 없음" if r is None else _fmt(r[1]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US RSI(2) 평균회귀 백테스트")
    parser.add_argument("--split", action="store_true", help="전체/하락/회복/최근 4구간 출력")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    parser.add_argument("--limit", type=int, help="앞 N종목만 (빠른 점검용)")
    args = parser.parse_args()

    tickers = load_us_universe()
    if args.limit:
        tickers = tickers[:args.limit]
    print(f"US RSI(2) 백테스트: {len(tickers)}종목 (비용 왕복 {US_ROUND_TRIP_COST:.1%})")
    trades = collect_trades(tickers)

    if trades.empty:
        print("거래가 없습니다 (데이터 로드 실패 또는 신호 없음).")
    elif args.split:
        for label, s, e in SPLIT_WINDOWS:
            report_window(label, trades, s, e)
    else:
        report_window("결과", trades, args.start, args.end)
