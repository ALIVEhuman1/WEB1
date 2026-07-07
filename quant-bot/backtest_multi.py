"""여러 매매법 백테스트 + 멀티 전략 포트폴리오 검증 (일봉 기반).

전략 (동일 비용 모델: 수수료 0.015%x2 + 거래세 0.18% + 슬리피지 0.1%):
- meanrev  평균회귀: 3일 연속 하락 & 200일선 위(장기 상승 종목의 눌림) -> 종가 매수,
           5일선 회복 또는 최대 5일 보유 후 종가 매도
- trend    추세추종: 5일선이 20일선 상향돌파 -> 익일 시가 매수, 하향돌파 -> 익일 시가 매도
- breakout 변동성 돌파: 기존 확정 규칙 (K=0.8, 거래량/시장 필터, 익일시가 청산), 고정 watchlist

유니버스: meanrev/trend는 전 종목 중 시그널 시점의 60일 평균 거래대금 10억원 이상
(유동성 없는 종목의 비현실적 체결 배제). breakout은 기존 watchlist 50종목.

포트폴리오 결합: 각 전략에 자본을 균등 배분했다고 가정하고, 전략별 일별 수익률의
평균으로 결합 수익 곡선을 만든다. 전략 간 상관관계도 출력한다.

사용법:
    python backtest_multi.py                          # 3개 전략 + 결합, 전체 기간
    python backtest_multi.py --start 20250101         # 구간 지정
    python backtest_multi.py --strategies meanrev,trend
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


def run_strategy(name: str, start_date: str | None, end_date: str | None) -> tuple[pd.DataFrame, dict] | None:
    """전략 실행 -> (거래 DataFrame, 요약 dict). 거래는 청산일 기준."""
    if name == "breakout":
        result = breakout_run_all(k=0.8, vol_filter=True, exit_open=True, market_filter=True,
                                  start_date=start_date, end_date=end_date)
        if result.empty:
            return None
        # 종목별 요약만 있으므로 거래 단위 재구성은 생략하고 일별 시계열은 별도 계산
        trades = _breakout_daily_trades(start_date, end_date)
    else:
        fn = meanrev_trades if name == "meanrev" else trend_trades
        all_trades = []
        for code in _all_stock_codes():
            df = _load(code)
            if df is None:
                continue
            all_trades.extend(fn(df))
        if not all_trades:
            return None
        trades = pd.DataFrame(all_trades)

    if start_date:
        trades = trades[trades["date"] >= start_date]
    if end_date:
        trades = trades[trades["date"] <= end_date]
    if trades.empty:
        return None

    daily = trades.groupby("date")["ret"].mean().sort_index()
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
    parser.add_argument("--strategies", type=str, default="breakout,meanrev,trend")
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
