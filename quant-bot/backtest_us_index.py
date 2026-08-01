"""US 지수 타이밍(절대 모멘텀) 백테스트: 종가>200일선이면 보유, 아니면 현금.

KR판 etf_timing.py의 미장 버전 검증. SPY/QQQ 일봉(yfinance)으로 돌린다.
핵심 질문: "빠지면 관망"만으로 매수후보유 대비 MDD를 얼마나 줄이는가?

미래참조 없음: 신호는 전일 종가>SMA200으로 확정하고 당일 수익률에 반영(1일 지연).
상태 전환(매수/매도)마다 왕복비용을 차감. 현금 구간은 0% (채권 이자 미가정, 보수적).

사용법:
    python backtest_us_index.py --split            # SPY/QQQ, 4구간
    python backtest_us_index.py --tickers SPY,QQQ,IWM --split
"""
import argparse

import numpy as np
import pandas as pd

from backtest_multi import _fmt, summarize

MA_DAYS = 200
SWITCH_COST = 0.001   # 전환 1회(편도) 수수료+슬리피지. 왕복이면 매수·매도 각 1회 차감
START = "2005-01-01"  # 2008 금융위기까지 포함해 하락장 회피력을 길게 검증

SPLIT_WINDOWS = [
    ("전체", None, None),
    ("금융위기 08-09", "2007-06-01", "2010-01-01"),
    ("하락장 2022", "2022-01-01", "2023-01-01"),
    ("최근 23~", "2023-01-01", None),
]


def load_prices(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(ticker, start=START, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.sort_index()


def timing_backtest(df: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """200일선 타이밍. 반환: (일별 전략 수익률, 라운드트립 거래목록)."""
    c = df["Close"].astype(float)
    sma = c.rolling(MA_DAYS).mean()
    ret = c.pct_change().to_numpy()
    sig = (c > sma).to_numpy()          # 종가 기준 신호
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    n = len(c)

    daily: dict[str, float] = {}
    trades: list[dict] = []
    in_pos = False        # 오늘 장중 보유 여부(어제 신호로 결정)
    entry_i = 0
    entry_c = 0.0
    for t in range(MA_DAYS, n):
        hold_today = bool(sig[t - 1])   # 1일 지연: 어제 종가 신호로 오늘 보유 결정
        r = ret[t] if hold_today else 0.0
        # 상태 전환 비용: 어제 보유상태(in_pos)와 오늘 목표가 다르면 편도 비용 1회
        if hold_today != in_pos:
            r -= SWITCH_COST
        daily[dates[t]] = r

        if hold_today and not in_pos:                 # 진입
            entry_i, entry_c = t, c.iloc[t]
        elif in_pos and not hold_today:               # 청산 -> 라운드트립 기록
            trades.append({"date": dates[t], "ret": c.iloc[t] / entry_c - 1 - 2 * SWITCH_COST,
                           "hold": t - entry_i})
        in_pos = hold_today
    if in_pos:
        trades.append({"date": dates[-1], "ret": c.iloc[-1] / entry_c - 1 - SWITCH_COST,
                       "hold": n - 1 - entry_i})
    return pd.Series(daily).sort_index(), pd.DataFrame(trades)


def buyhold_line(df: pd.DataFrame, s, e) -> str:
    """같은 구간 매수후보유 벤치마크(누적/MDD)."""
    c = df["Close"].astype(float)
    c.index = [d.strftime("%Y-%m-%d") for d in df.index]
    if s:
        c = c[c.index >= s]
    if e:
        c = c[c.index <= e]
    if len(c) < 2:
        return "구간 데이터 부족"
    eq = c / c.iloc[0]
    mdd = (eq / eq.cummax() - 1).min()
    return f"누적 {eq.iloc[-1] - 1:+.1%} | MDD {mdd:.1%}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US 지수 타이밍(200일선) 백테스트")
    parser.add_argument("--tickers", type=str, default="SPY,QQQ")
    parser.add_argument("--split", action="store_true", help="전체/금융위기/2022/최근 4구간")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    print(f"US 지수타이밍(SMA{MA_DAYS}): {', '.join(tickers)} | 전환비용 편도 {SWITCH_COST:.1%} | {START}~")

    data = {}
    for tk in tickers:
        df = load_prices(tk)
        if df is None or len(df) < MA_DAYS + 20:
            print(f"  {tk}: 데이터 부족, 건너뜀")
            continue
        data[tk] = df

    windows = SPLIT_WINDOWS if args.split else [("결과", args.start, args.end)]
    for label, s, e in windows:
        print(f"\n===== {label} ({s or '처음'} ~ {e or '현재'}) =====")
        for tk, df in data.items():
            daily, trades = timing_backtest(df)
            r = summarize(f"{tk}타이밍", daily, trades, s, e)
            print(f"  {tk:>4} 타이밍 | " + ("구간 없음" if r is None else _fmt(r[1])))
            print(f"  {tk:>4} 매수보유 | {buyhold_line(df, s, e)}")
