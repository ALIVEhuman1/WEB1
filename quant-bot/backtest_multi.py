"""여러 매매법 백테스트 + 멀티 전략 포트폴리오 검증 (일봉 기반).

전략 (동일 비용 모델: 수수료 0.015%x2 + 거래세 0.18% + 슬리피지 0.1%):
- breakout   변동성 돌파: 기존 확정 규칙 (K=0.8, 거래량/시장 필터, 익일시가 청산), 고정 watchlist
- momentum   횡단면 모멘텀: 매월 말 최근 6개월 수익률 상위 20종목 매수, 한 달 보유 후 리밸런스
- high52     52주 신고가 돌파: 종가가 직전 52주 최고가 돌파 -> 익일 시가 매수, 20일선 이탈 -> 익일 시가 매도
- index      지수 타이밍(절대 모멘텀): 코스피 종가 > 200일선이면 지수 보유, 아니면 현금
- meanrev    평균회귀 (2026-07 검증 탈락: 전 구간 거래당 마이너스 -> 참고용으로만 유지)
- trend      5/20 골든크로스 (2026-07 검증 탈락: 하락/횡보장 거래당 -1~-2% -> 참고용으로만 유지)

유니버스: 종목 단위 전략은 전 종목 중 시그널 시점의 60일 평균 거래대금 10억원 이상
(유동성 없는 종목의 비현실적 체결 배제). breakout은 기존 watchlist 50종목.
index는 코스피 지수(KS11)를 ETF로 추종한다고 가정 (거래세 없음, 비용 0.15%/전환).

포트폴리오 결합: 각 전략에 자본을 균등 배분했다고 가정하고, 전략별 일별 수익률의
평균으로 결합 수익 곡선을 만든다. 전략 간 상관관계도 출력한다.

사용법:
    python backtest_multi.py                          # 기본 4개 전략 + 결합, 전체 기간
    python backtest_multi.py --start 20250101         # 구간 지정
    python backtest_multi.py --strategies momentum,index
"""
import argparse

import pandas as pd

import db
from backtest import FEE_RATE, SLIPPAGE_RATE, TAX_RATE
from backtest import run_all as breakout_run_all

INDEX_CODE = "KS11"
MIN_TURNOVER = 1_000_000_000  # 유동성 필터: 60일 평균 거래대금 10억원
ROUND_TRIP_COST = FEE_RATE * 2 + TAX_RATE


def _all_stock_codes() -> list[str]:
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT stock_code FROM daily_candles WHERE stock_code != ?", (INDEX_CODE,)
        ).fetchall()
    return [r[0] for r in rows]


def _load(code: str) -> pd.DataFrame | None:
    df = db.get_daily_candles_df(code)
    if len(df) < 220:
        return None
    df = df.sort_values("date").reset_index(drop=True)
    df["turnover_ma"] = (df["close"].astype(float) * df["volume"]).rolling(60).mean()
    return df


def meanrev_trades(df: pd.DataFrame) -> list[dict]:
    """3일 연속 하락 & 200일선 위 -> 종가 매수, 5일선 회복 or 5일 후 종가 매도."""
    c = df["close"].astype(float)
    ma5 = c.rolling(5).mean()
    ma200 = c.rolling(200).mean()
    down3 = (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3))
    signal = down3 & (c > ma200) & (df["turnover_ma"] > MIN_TURNOVER)

    trades = []
    i, n = 0, len(df)
    idx = signal[signal].index
    for t in idx:
        if t < i or t + 1 >= n:  # 보유 중 중복 진입 방지 / 데이터 끝
            continue
        entry = c[t] * (1 + SLIPPAGE_RATE)
        exit_i = min(t + 5, n - 1)
        for u in range(t + 1, min(t + 6, n)):
            if c[u] > ma5[u]:
                exit_i = u
                break
        ret = (c[exit_i] / entry) * (1 - ROUND_TRIP_COST) - 1
        trades.append({"date": df["date"][exit_i], "ret": ret, "hold": exit_i - t})
        i = exit_i + 1
    return trades


def trend_trades(df: pd.DataFrame) -> list[dict]:
    """5일선이 20일선 상향돌파 -> 익일 시가 매수, 하향돌파 -> 익일 시가 매도."""
    c = df["close"].astype(float)
    o = df["open"].astype(float)
    ma5 = c.rolling(5).mean()
    ma20 = c.rolling(20).mean()
    cross_up = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
    cross_dn = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))

    trades = []
    n = len(df)
    holding_from = None
    entry_price = 0.0
    for t in range(21, n - 1):
        if holding_from is None:
            if cross_up[t] and df["turnover_ma"][t] > MIN_TURNOVER:
                holding_from = t + 1
                entry_price = o[t + 1] * (1 + SLIPPAGE_RATE)
        else:
            if cross_dn[t]:
                exit_price = o[t + 1]
                ret = (exit_price / entry_price) * (1 - ROUND_TRIP_COST) - 1
                trades.append({"date": df["date"][t + 1], "ret": ret, "hold": t + 1 - holding_from})
                holding_from = None
    return trades


def high52_trades(df: pd.DataFrame) -> list[dict]:
    """종가가 직전 52주(252일) 최고가 돌파 -> 익일 시가 매수, 20일선 이탈 -> 익일 시가 매도."""
    c = df["close"].astype(float)
    o = df["open"].astype(float)
    hi252 = c.shift(1).rolling(252).max()
    ma20 = c.rolling(20).mean()
    signal = (c > hi252) & (df["turnover_ma"] > MIN_TURNOVER)

    trades = []
    n = len(df)
    holding_from = None
    entry_price = 0.0
    for t in range(253, n - 1):
        if holding_from is None:
            if signal[t]:
                holding_from = t + 1
                entry_price = o[t + 1] * (1 + SLIPPAGE_RATE)
        else:
            if c[t] < ma20[t]:
                exit_price = o[t + 1]
                ret = (exit_price / entry_price) * (1 - ROUND_TRIP_COST) - 1
                trades.append({"date": df["date"][t + 1], "ret": ret, "hold": t + 1 - holding_from})
                holding_from = None
    return trades


MOMENTUM_TOP_N = 20
MOMENTUM_LOOKBACK = 126  # 약 6개월


def momentum_series() -> tuple[pd.Series, pd.DataFrame]:
    """매월 말 6개월 수익률 상위 20종목 매수, 다음 달 보유. (일별 수익률, 거래 목록) 반환."""
    closes, turnovers = {}, {}
    for code in _all_stock_codes():
        df = db.get_daily_candles_df(code)
        if len(df) < 300:
            continue
        df = df.sort_values("date")
        s = pd.Series(df["close"].astype(float).values, index=df["date"].values)
        closes[code] = s
        turnovers[code] = pd.Series(
            (df["close"].astype(float) * df["volume"]).rolling(60).mean().values,
            index=df["date"].values)

    panel = pd.DataFrame(closes).sort_index()
    to_panel = pd.DataFrame(turnovers).reindex(panel.index)
    rets = panel.pct_change()

    dates = panel.index.to_list()
    month_ends = [dates[i] for i in range(len(dates) - 1) if dates[i][:6] != dates[i + 1][:6]]

    daily_parts, trade_rows = [], []
    prev_holdings: set = set()
    for mi, me in enumerate(month_ends):
        i = dates.index(me)
        if i < MOMENTUM_LOOKBACK:
            continue
        row_now, row_past, row_to = panel.loc[me], panel.iloc[i - MOMENTUM_LOOKBACK], to_panel.loc[me]
        mom = (row_now / row_past - 1).where(row_to > MIN_TURNOVER)
        top = set(mom.dropna().nlargest(MOMENTUM_TOP_N).index)
        if not top:
            continue

        next_me_i = dates.index(month_ends[mi + 1]) if mi + 1 < len(month_ends) else len(dates) - 1
        hold_dates = dates[i + 1:next_me_i + 1]
        if not hold_dates:
            continue

        block = rets.loc[hold_dates, list(top)].mean(axis=1)
        # 리밸런스 비용: 교체된 종목 비율만큼 첫날 수익률에서 차감
        changed = len(top - prev_holdings)
        block.iloc[0] -= (changed / len(top)) * (ROUND_TRIP_COST + SLIPPAGE_RATE)
        daily_parts.append(block)

        for code in top:
            entry, exit_ = panel.loc[me, code], panel.loc[hold_dates[-1], code]
            if pd.notna(entry) and pd.notna(exit_):
                cost = (ROUND_TRIP_COST + SLIPPAGE_RATE) if code not in prev_holdings else 0.0
                trade_rows.append({"date": hold_dates[-1], "ret": exit_ / entry - 1 - cost,
                                   "hold": len(hold_dates)})
        prev_holdings = top

    daily = pd.concat(daily_parts).fillna(0.0) if daily_parts else pd.Series(dtype=float)
    return daily, pd.DataFrame(trade_rows)


INDEX_SWITCH_COST = 0.0015  # ETF 왕복 비용 가정 (거래세 없음)


def index_series() -> tuple[pd.Series, pd.DataFrame]:
    """코스피 종가 > 200일선이면 보유, 아니면 현금 (절대 모멘텀, ETF 추종 가정)."""
    df = db.get_daily_candles_df(INDEX_CODE).sort_values("date").reset_index(drop=True)
    c = df["close"].astype(float)
    ma200 = c.rolling(200).mean()
    pos = (c > ma200).shift(1, fill_value=False)  # 전일 종가 기준 판단, 당일부터 반영
    ret = c.pct_change().fillna(0.0) * pos
    switch = pos != pos.shift(1, fill_value=False)
    ret[switch] -= INDEX_SWITCH_COST / 2  # 진입/청산 각각 절반씩

    daily = pd.Series(ret.values, index=df["date"].values)

    trade_rows, entry_i = [], None
    for t in range(len(df)):
        if pos[t] and entry_i is None:
            entry_i = t
        elif not pos[t] and entry_i is not None:
            r = c[t - 1] / c[entry_i] - 1 - INDEX_SWITCH_COST
            trade_rows.append({"date": df["date"][t - 1], "ret": r, "hold": t - entry_i})
            entry_i = None
    if entry_i is not None:
        trade_rows.append({"date": df["date"].iloc[-1],
                           "ret": c.iloc[-1] / c[entry_i] - 1 - INDEX_SWITCH_COST,
                           "hold": len(df) - entry_i})
    return daily, pd.DataFrame(trade_rows)


PER_STOCK_STRATEGIES = {"meanrev": meanrev_trades, "trend": trend_trades, "high52": high52_trades}


def run_strategy(name: str, start_date: str | None, end_date: str | None) -> tuple[pd.DataFrame, dict] | None:
    """전략 실행 -> (일별 수익률 Series, 요약 dict). 거래는 청산일 기준."""
    daily = None
    if name == "breakout":
        trades = _breakout_daily_trades(start_date, end_date)
    elif name == "momentum":
        daily, trades = momentum_series()
    elif name == "index":
        daily, trades = index_series()
    elif name in PER_STOCK_STRATEGIES:
        fn = PER_STOCK_STRATEGIES[name]
        all_trades = []
        for code in _all_stock_codes():
            df = _load(code)
            if df is None:
                continue
            all_trades.extend(fn(df))
        trades = pd.DataFrame(all_trades)
    else:
        raise ValueError(f"알 수 없는 전략: {name}")

    if trades.empty:
        return None
    if start_date:
        trades = trades[trades["date"] >= start_date]
    if end_date:
        trades = trades[trades["date"] <= end_date]
    if trades.empty:
        return None

    if daily is None:
        daily = trades.groupby("date")["ret"].mean().sort_index()
    else:
        if start_date:
            daily = daily[daily.index >= start_date]
        if end_date:
            daily = daily[daily.index <= end_date]
        if daily.empty:
            return None

    equity = (1 + daily).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    summary = {
        "strategy": name,
        "trades": len(trades),
        "win_rate": (trades["ret"] > 0).mean(),
        "avg_trade_return": trades["ret"].mean(),
        "avg_hold_days": trades["hold"].mean() if "hold" in trades else 1.0,
        "cum_return": equity.iloc[-1] - 1,
        "mdd": mdd,
        "period": f"{daily.index[0]}~{daily.index[-1]}",
    }
    return daily, summary


def _breakout_daily_trades(start_date, end_date) -> pd.DataFrame:
    """변동성 돌파의 거래 목록 (기존 확정 규칙, 고정 watchlist)."""
    from backtest import VOL_WINDOW, _load_market_regime
    from main import load_watchlist

    regime = _load_market_regime()
    rows = []
    for code in load_watchlist():
        df = db.get_daily_candles_df(code)
        if len(df) < VOL_WINDOW + 10:
            continue
        df = df.sort_values("date").reset_index(drop=True)
        df["prev_range"] = (df["high"] - df["low"]).shift(1)
        df["target"] = df["open"] + 0.8 * df["prev_range"]
        prev_vol = df["volume"].shift(1)
        vol_ma = df["volume"].rolling(VOL_WINDOW).mean().shift(1)
        allowed = (prev_vol > vol_ma) & df["date"].map(lambda d: bool(regime.get(d, False)))
        df["exit_price"] = df["open"].shift(-1)
        df = df.dropna().reset_index(drop=True)
        hit = (df["high"] >= df["target"]) & allowed.reindex(df.index, fill_value=False)
        buy = df.loc[hit, "target"] * (1 + SLIPPAGE_RATE)
        sell = df.loc[hit, "exit_price"]
        ret = (sell / buy) * (1 - ROUND_TRIP_COST) - 1
        for d, r in zip(df.loc[hit, "date"], ret):
            rows.append({"date": d, "ret": r, "hold": 1})
    return pd.DataFrame(rows)


def combine(dailies: dict[str, pd.Series]) -> dict:
    """전략별 자본 균등 배분 가정으로 결합 수익 곡선 계산 + 상관관계."""
    aligned = pd.DataFrame(dailies).fillna(0.0).sort_index()
    combined = aligned.mean(axis=1)
    equity = (1 + combined).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    return {
        "cum_return": equity.iloc[-1] - 1,
        "mdd": mdd,
        "correlation": aligned.corr(),
    }


def _fmt(s: dict) -> str:
    return (f"{s['strategy']:>9} | 거래 {s['trades']:5d}건 | 승률 {s['win_rate']:.1%} | "
            f"거래당 {s['avg_trade_return']:+.3%} | 평균보유 {s['avg_hold_days']:.1f}일 | "
            f"누적 {s['cum_return']:+.1%} | MDD {s['mdd']:.1%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="멀티 전략 백테스트")
    parser.add_argument("--strategies", type=str, default="breakout,momentum,high52,index")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    args = parser.parse_args()

    db.init_db()
    names = [s.strip() for s in args.strategies.split(",")]

    dailies = {}
    print(f"기간: {args.start or '전체'} ~ {args.end or '현재'}")
    for name in names:
        result = run_strategy(name, args.start, args.end)
        if result is None:
            print(f"{name:>9} | 데이터/거래 없음")
            continue
        daily, summary = result
        dailies[name] = daily
        print(_fmt(summary))

    if len(dailies) >= 2:
        c = combine(dailies)
        print()
        print(f"[결합 포트폴리오 (자본 균등배분)] 누적 {c['cum_return']:+.1%} | MDD {c['mdd']:.1%}")
        print("전략 간 상관관계:")
        print(c["correlation"].round(2).to_string())
