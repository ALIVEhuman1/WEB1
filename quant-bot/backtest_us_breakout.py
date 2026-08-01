"""US 신고가 돌파 추세추종 백테스트 (돈치안 채널 + 시장필터 + ATR 트레일링).

②전략 검증: 미장은 모멘텀이 강해 '강한 종목이 계속 강하다'. 개별종목이 N일
신고가(종가 기준)를 돌파하면 매수, 상승분을 ATR 트레일링(샹들리에)으로 따라가다
꺾이면 청산. KR에서 breakout을 살린 그 시장필터(지수>200일선일 때만 진입)를 그대로
얹어 하락장 진입을 원천 차단한다.

두 관점(backtest_us_rsi2.py와 동일 구조):
- 신호(전수): 모든 돌파를 독립 거래로 본 '거래당 엣지'
- N종목 시뮬: 동시 최대 N종목, 모멘텀 강한 순 우선, 익일 시가 체결 자본곡선

미래참조 없음: 신호는 당일 종가로 확정 -> 익일 시가 체결. 시장필터는 SPY 당일
종가>SMA200 (개장 전 확정). 트레일링은 진입 후 최고종가 기준(후행).

사용법:
    python backtest_us_breakout.py --split
    python backtest_us_breakout.py --split --no-filter        # 시장필터 끄고 비교
    python backtest_us_breakout.py --split --entry 50 --atr-mult 2.5
"""
import argparse
import time

import numpy as np
import pandas as pd

from backtest_multi import _fmt, summarize
from us_universe import load_us_universe

SLIPPAGE_RATE = 0.001
US_ROUND_TRIP_COST = 0.002
DONCHIAN_ENTRY = 100      # N일 신고가(종가) 돌파
ATR_PERIOD = 20
ATR_MULT = 3.0            # 샹들리에 트레일링 폭 (진입후 최고종가 - MULT*ATR)
MOM_LOOKBACK = 100        # 슬롯 경쟁 시 모멘텀 랭킹용
SMA_LONG = 200            # 시장필터(SPY)용
BENCHMARK = "SPY"
START = "2005-01-01"

SPLIT_WINDOWS = [
    ("전체", None, None),
    ("금융위기 08-09", "2007-06-01", "2010-01-01"),
    ("하락장 2022", "2022-01-01", "2023-01-01"),
    ("최근 23~", "2023-01-01", None),
]


def atr_series(high, low, close, period=ATR_PERIOD) -> np.ndarray:
    """와일더 ATR."""
    prev_c = close.shift(1)
    tr = pd.concat([high - low, (high - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean().to_numpy()


def compute_signals(df: pd.DataFrame) -> dict:
    df = df.sort_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"].astype(float)
    h = df["High"].astype(float)
    low = df["Low"].astype(float)
    donch = c.shift(1).rolling(DONCHIAN_ENTRY).max()   # 전일까지의 N일 최고종가(오늘 제외)
    mom = c / c.shift(MOM_LOOKBACK) - 1
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "o": df["Open"].to_numpy(float),
        "c": c.to_numpy(),
        "donch": donch.to_numpy(),
        "atr": atr_series(h, low, c),
        "mom": mom.to_numpy(),
    }


def market_regime(bench: pd.DataFrame) -> dict:
    """SPY 종가>SMA200이면 True인 날짜->bool 맵."""
    bench = bench.sort_index()
    if isinstance(bench.columns, pd.MultiIndex):
        bench.columns = bench.columns.get_level_values(0)
    c = bench["Close"].astype(float)
    ok = (c > c.rolling(SMA_LONG).mean()).fillna(False)
    return {d.strftime("%Y-%m-%d"): bool(v) for d, v in ok.items()}


START_IDX = max(DONCHIAN_ENTRY, ATR_PERIOD, MOM_LOOKBACK) + 1


def breakout_trades(sig: dict, market_ok: dict) -> list[dict]:
    """신호 전수 뷰: 한 종목 한 번에 하나. 진입 후 ATR 트레일링으로 청산."""
    o, c, donch, atr = sig["o"], sig["c"], sig["donch"], sig["atr"]
    dates = sig["dates"]
    n = len(c)
    if n < START_IDX + 5:
        return []
    trades, hold_i, entry_price, peak = [], None, 0.0, -np.inf
    for t in range(START_IDX, n - 1):
        if hold_i is None:
            if market_ok.get(dates[t], False) and not np.isnan(donch[t]) and c[t] > donch[t]:
                hold_i, entry_price, peak = t + 1, o[t + 1] * (1 + SLIPPAGE_RATE), -np.inf
            continue
        u = t
        if u < hold_i:
            continue
        peak = max(peak, c[u])
        if np.isnan(atr[u]):
            continue
        if c[u] < peak - ATR_MULT * atr[u]:
            trades.append({"date": dates[u + 1], "ret": (o[u + 1] / entry_price) * (1 - US_ROUND_TRIP_COST) - 1,
                           "hold": u + 1 - hold_i})
            hold_i = None
    if hold_i is not None:
        trades.append({"date": dates[-1], "ret": (c[-1] / entry_price) * (1 - US_ROUND_TRIP_COST) - 1,
                       "hold": n - 1 - hold_i})
    return trades


def portfolio_sim(data: dict, market_ok: dict, n_positions: int) -> tuple[pd.Series, pd.DataFrame]:
    """동시 최대 n_positions종목, 모멘텀 강한 순 우선, 익일 시가 체결."""
    calendar = sorted({d for sig in data.values() for d in sig["dates"]})
    idxmap = {tk: {d: i for i, d in enumerate(sig["dates"])} for tk, sig in data.items()}

    held: dict[str, dict] = {}   # tk -> {e, entry_price, egi, peak}
    pend_buy: list[str] = []
    pend_sell: list[str] = []
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

        # 2) 캐리 보유분: 오늘 종가 수익 반영, 트레일링 이탈이면 내일 매도 예약
        for tk, pos in list(held.items()):
            if pos["egi"] == gi:      # 오늘 산 종목은 3)에서 처리
                continue
            ti = idxmap[tk].get(gd)
            if ti is None:
                continue
            sig = data[tk]
            slot_returns.append(sig["c"][ti] / sig["c"][ti - 1] - 1)
            pos["peak"] = max(pos["peak"], sig["c"][ti])
            atr = sig["atr"][ti]
            if not np.isnan(atr) and sig["c"][ti] < pos["peak"] - ATR_MULT * atr:
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
            held[tk] = {"e": ti, "entry_price": entry_price, "egi": gi, "peak": sig["c"][ti]}
            slot_returns.append(sig["c"][ti] / entry_price - 1 - US_ROUND_TRIP_COST)
        pend_buy = []

        # 4) 오늘 신규 돌파 신호 -> 내일 매수 예약 (모멘텀 강한 순), 시장필터 통과 시만
        if market_ok.get(gd, False):
            cands = []
            for tk, sig in data.items():
                if tk in held:
                    continue
                ti = idxmap[tk].get(gd)
                if ti is None or ti < START_IDX or np.isnan(sig["donch"][ti]):
                    continue
                if sig["c"][ti] > sig["donch"][ti]:
                    m = sig["mom"][ti]
                    cands.append((-(m if not np.isnan(m) else -9), tk))
            cands.sort()
            pend_buy = [tk for _, tk in cands[:n_positions]]
        else:
            pend_buy = []

        daily_ret[gd] = sum(slot_returns) / n_positions   # 빈 슬롯=현금(0)

    return pd.Series(daily_ret).sort_index(), pd.DataFrame(trades)


def load_prices(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.download(ticker, start=START, auto_adjust=True, progress=False)


def load_all(tickers: list[str]) -> dict:
    data, failed = {}, []
    for i, tk in enumerate(tickers, 1):
        try:
            df = load_prices(tk)
            if df is None or len(df) < START_IDX + 20:
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
    parser = argparse.ArgumentParser(description="US 신고가 돌파 추세추종 백테스트")
    parser.add_argument("--split", action="store_true", help="전체/금융위기/2022/최근 4구간")
    parser.add_argument("--no-filter", action="store_true", help="시장필터(SPY>200일선) 끄고 비교")
    parser.add_argument("--positions", type=int, default=5, help="동시 보유 슬롯 수 (기본 5)")
    parser.add_argument("--entry", type=int, default=DONCHIAN_ENTRY, help="돈치안 진입 기간(일)")
    parser.add_argument("--atr-mult", type=float, default=ATR_MULT, help="ATR 트레일링 배수")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    parser.add_argument("--limit", type=int, help="앞 N종목만 (빠른 점검)")
    args = parser.parse_args()

    DONCHIAN_ENTRY = args.entry
    ATR_MULT = args.atr_mult
    START_IDX = max(DONCHIAN_ENTRY, ATR_PERIOD, MOM_LOOKBACK) + 1

    tickers = load_us_universe()
    if args.limit:
        tickers = tickers[:args.limit]
    filt_txt = "끔(대조군)" if args.no_filter else f"{BENCHMARK}>SMA{SMA_LONG}"
    print(f"US 돌파추세: {len(tickers)}종목 | 진입 {DONCHIAN_ENTRY}일신고가 | 트레일 ATR×{ATR_MULT} | "
          f"시장필터 {filt_txt} | 슬롯 {args.positions}")

    data = load_all(tickers)
    if not data:
        print("데이터 로드 실패로 종료")
        raise SystemExit(1)

    if args.no_filter:
        market_ok = {d: True for sig in data.values() for d in sig["dates"]}
    else:
        bench = load_prices(BENCHMARK)
        market_ok = market_regime(bench)

    all_trades = pd.DataFrame([t for sig in data.values() for t in breakout_trades(sig, market_ok)])
    sim_daily, sim_trades = portfolio_sim(data, market_ok, args.positions)

    windows = SPLIT_WINDOWS if args.split else [("결과", args.start, args.end)]
    for label, s, e in windows:
        print(f"\n===== {label} ({s or '처음'} ~ {e or '현재'}) =====")
        _line("신호(전수) ", "돌파", None, all_trades, s, e)
        _line(f"{args.positions}종목시뮬  ", f"돌파×{args.positions}", sim_daily, sim_trades, s, e)
