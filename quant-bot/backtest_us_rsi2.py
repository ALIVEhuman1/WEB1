"""US RSI(2) 평균회귀 백테스트 (래리 코너스, yfinance 일봉).

두 관점으로 검증한다:
- 신호(전수): 모든 진입 신호를 독립 거래로 본 '거래당 엣지' (편향 없는 신호 품질)
- 5종목 시뮬: 실제로 동시 최대 N종목만, RSI 낮은 순 우선, 익일 시가 체결로 굴린
  현실적 자본곡선 (누적/MDD가 정직함 — 신호가 급락일에 몰리는 아티팩트 제거)

규칙: 종가>SMA200 필터, RSI(2)<RSI_ENTRY 진입(익일 시가), 청산은 종가>SMA5(익일
시가) 또는 10거래일 상한. 손절(-7%)은 코너스 원본엔 없어 기본 비활성(--stop로 켬).

사용법:
    python backtest_us_rsi2.py --split                 # 원본(손절 없음) 4구간
    python backtest_us_rsi2.py --split --stop 0.07     # -7% 손절 켜서 비교
    python backtest_us_rsi2.py --split --positions 5   # 동시 보유 슬롯 수
    python backtest_us_rsi2.py --limit 20 --split      # 앞 20종목만 (빠른 점검)
"""
import argparse
import time

import numpy as np
import pandas as pd

from backtest_multi import _fmt, summarize  # 리포트 형식 재사용
from us_universe import load_us_universe

SLIPPAGE_RATE = 0.001          # 편도 슬리피지
US_ROUND_TRIP_COST = 0.002     # 미국은 거래세 없음: 수수료+슬리피지 왕복 가정
RSI_PERIOD = 2
RSI_ENTRY = 5.0
SMA_LONG = 200
SMA_SHORT = 5
MAX_HOLD_DAYS = 10
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


def compute_signals(df: pd.DataFrame) -> dict:
    """티커 일봉 -> 전략 계산용 배열 묶음 (모두 후행, 미래 참조 없음)."""
    df = df.sort_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"].astype(float)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "o": df["Open"].to_numpy(float),
        "low": df["Low"].to_numpy(float),
        "c": c.to_numpy(),
        "sma200": c.rolling(SMA_LONG).mean().to_numpy(),
        "sma5": c.rolling(SMA_SHORT).mean().to_numpy(),
        "rsi": rsi_series(c),
    }


def rsi2_trades(sig: dict, stop: float) -> list[dict]:
    """신호 전수 뷰: 한 종목을 한 번에 하나씩 잡는 독립 거래 목록 (거래당 엣지 측정)."""
    o, low, c = sig["o"], sig["low"], sig["c"]
    sma200, sma5, rsi = sig["sma200"], sig["sma5"], sig["rsi"]
    dates = sig["dates"]
    n = len(c)
    if n < SMA_LONG + 5:
        return []

    trades, hold_i, entry_price = [], None, 0.0
    for t in range(SMA_LONG, n - 1):
        if hold_i is None:
            if c[t] > sma200[t] and rsi[t] < RSI_ENTRY:
                hold_i = t + 1
                entry_price = o[t + 1] * (1 + SLIPPAGE_RATE)
            continue
        u = t
        if u < hold_i:
            continue
        if stop > 0 and low[u] <= entry_price * (1 - stop):
            lvl = entry_price * (1 - stop)
            trades.append({"date": dates[u], "ret": (lvl / entry_price) * (1 - US_ROUND_TRIP_COST) - 1,
                           "hold": u - hold_i + 1})
            hold_i = None
            continue
        if c[u] > sma5[u] or u - hold_i >= MAX_HOLD_DAYS - 1:
            trades.append({"date": dates[u + 1], "ret": (o[u + 1] / entry_price) * (1 - US_ROUND_TRIP_COST) - 1,
                           "hold": u + 1 - hold_i})
            hold_i = None
            continue
    if hold_i is not None:
        trades.append({"date": dates[-1], "ret": (c[-1] / entry_price) * (1 - US_ROUND_TRIP_COST) - 1,
                       "hold": n - 1 - hold_i})
    return trades


def portfolio_sim(data: dict, n_positions: int, stop: float) -> tuple[pd.Series, pd.DataFrame]:
    """동시 최대 n_positions종목, RSI 낮은 순 우선, 익일 시가 체결로 굴린 현실적 시뮬.
    반환: (일별 포트폴리오 수익률 시계열, 실현 거래 목록)."""
    calendar = sorted({d for sig in data.values() for d in sig["dates"]})
    idxmap = {tk: {d: i for i, d in enumerate(sig["dates"])} for tk, sig in data.items()}

    held: dict[str, dict] = {}   # tk -> {e, entry_price, egi}
    pend_buy: list[str] = []     # 어제 확정, 오늘 시가 매수 대기
    pend_sell: list[str] = []    # 어제 확정, 오늘 시가 매도 대기
    daily_ret: dict[str, float] = {}
    trades: list[dict] = []

    for gi, gd in enumerate(calendar):
        slot_returns: list[float] = []

        # 1) 매도 집행 (어제 확정) — 오늘 시가
        keep_sell = []
        for tk in pend_sell:
            pos = held.get(tk)
            if pos is None:
                continue
            ti = idxmap[tk].get(gd)
            if ti is None:
                keep_sell.append(tk)
                continue
            sig = data[tk]
            slot_returns.append(sig["o"][ti] / sig["c"][ti - 1] - 1)
            trades.append({"date": gd, "tk": tk, "ret": sig["o"][ti] / pos["entry_price"] - 1 - US_ROUND_TRIP_COST,
                           "hold": ti - pos["e"]})
            del held[tk]
        pend_sell = keep_sell

        # 2) 캐리 보유분: 손절(당일)/중간보유 수익, 청산신호면 내일 매도 예약
        for tk, pos in list(held.items()):
            if pos["egi"] == gi:      # 오늘 산 종목은 3)에서 처리
                continue
            ti = idxmap[tk].get(gd)
            if ti is None:
                continue
            sig = data[tk]
            prev_c = sig["c"][ti - 1]
            if stop > 0 and sig["low"][ti] <= pos["entry_price"] * (1 - stop):
                lvl = pos["entry_price"] * (1 - stop)
                slot_returns.append(lvl / prev_c - 1)
                trades.append({"date": gd, "tk": tk, "ret": lvl / pos["entry_price"] - 1 - US_ROUND_TRIP_COST,
                               "hold": ti - pos["e"]})
                del held[tk]
                continue
            slot_returns.append(sig["c"][ti] / prev_c - 1)
            if sig["c"][ti] > sig["sma5"][ti] or ti - pos["e"] >= MAX_HOLD_DAYS - 1:
                pend_sell.append(tk)

        # 3) 매수 집행 (어제 확정) — 오늘 시가, 빈 슬롯만큼
        for tk in pend_buy:
            if len(held) >= n_positions:
                break
            ti = idxmap[tk].get(gd)
            if ti is None or tk in held:
                continue
            sig = data[tk]
            entry_price = sig["o"][ti] * (1 + SLIPPAGE_RATE)
            held[tk] = {"e": ti, "entry_price": entry_price, "egi": gi}
            slot_returns.append(sig["c"][ti] / entry_price - 1 - US_ROUND_TRIP_COST)  # 진입일 + 왕복비용
        pend_buy = []

        # 4) 오늘 신규 진입 신호 탐지 -> 내일 매수 예약 (RSI 낮은 순)
        cands = []
        for tk, sig in data.items():
            if tk in held:
                continue
            ti = idxmap[tk].get(gd)
            if ti is None or ti == 0 or np.isnan(sig["sma200"][ti]):
                continue
            if sig["c"][ti] > sig["sma200"][ti] and sig["rsi"][ti] < RSI_ENTRY:
                cands.append((sig["rsi"][ti], tk))
        cands.sort()
        pend_buy = [tk for _, tk in cands[:n_positions]]

        daily_ret[gd] = sum(slot_returns) / n_positions  # 빈 슬롯=현금(0), 현금 드래그 반영

    return pd.Series(daily_ret).sort_index(), pd.DataFrame(trades)


def load_prices(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.download(ticker, start=START, auto_adjust=True, progress=False)


def load_all(tickers: list[str]) -> dict:
    data, failed = {}, []
    for i, tk in enumerate(tickers, 1):
        try:
            df = load_prices(tk)
            if df is None or len(df) < SMA_LONG + 20:
                continue
            data[tk] = compute_signals(df)
        except Exception as exc:
            failed.append(f"{tk}({exc})")
        time.sleep(0.3)
        if i % 20 == 0:
            print(f"  ... 로드/계산 {i}/{len(tickers)}")
    if failed:
        print(f"[로드 실패 {len(failed)}종목] {', '.join(failed[:8])}{' ...' if len(failed) > 8 else ''}")
    return data


def _line(tag: str, name: str, daily, trades, s, e) -> None:
    r = summarize(name, daily, trades, s, e)
    print(f"  {tag} " + ("거래 없음" if r is None else _fmt(r[1])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US RSI(2) 평균회귀 백테스트")
    parser.add_argument("--split", action="store_true", help="전체/하락/회복/최근 4구간")
    parser.add_argument("--stop", type=float, default=0.0, help="손절 비율(예 0.07). 기본 0=손절 없음(원본)")
    parser.add_argument("--positions", type=int, default=5, help="동시 보유 슬롯 수 (기본 5)")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    parser.add_argument("--limit", type=int, help="앞 N종목만 (빠른 점검)")
    args = parser.parse_args()

    tickers = load_us_universe()
    if args.limit:
        tickers = tickers[:args.limit]
    stop_txt = f"{args.stop:.0%}" if args.stop > 0 else "없음(원본)"
    print(f"US RSI(2): {len(tickers)}종목 | 손절 {stop_txt} | 슬롯 {args.positions} | 비용 왕복 {US_ROUND_TRIP_COST:.1%}")

    data = load_all(tickers)
    if not data:
        print("데이터 로드 실패로 종료")
        raise SystemExit(1)

    all_trades = pd.DataFrame([t for sig in data.values() for t in rsi2_trades(sig, args.stop)])
    sim_daily, sim_trades = portfolio_sim(data, args.positions, args.stop)

    windows = SPLIT_WINDOWS if args.split else [("결과", args.start, args.end)]
    for label, s, e in windows:
        print(f"\n===== {label} ({s or '처음'} ~ {e or '현재'}) =====")
        _line("신호(전수) ", "rsi2", None, all_trades, s, e)
        _line("5종목시뮬  ", f"rsi2×{args.positions}", sim_daily, sim_trades, s, e)
