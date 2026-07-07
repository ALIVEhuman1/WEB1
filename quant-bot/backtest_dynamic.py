"""동적 유니버스 백테스트: '매일 전일 거래대금 상위 N종목'을 감시하는 실제 운영 방식 재현.

고정 watchlist 백테스트(backtest.py)와의 차이:
- 감시 대상이 매 거래일 바뀐다 (전일 거래대금 상위 TOP_N, collect_market.py와 동일 규칙)
- 그 외 규칙(K 돌파, 거래량 필터, 시장 필터, 익일시가 청산, 비용)은 동일

한계 (일봉 데이터의 근본 제약):
- MAX_POSITIONS 제한은 장중 돌파 '순서'를 알 수 없어 모델링하지 않는다.
  당일 돌파된 종목 전체에 균등 배분했다고 가정한 근사치다.

사용법 (전 종목 데이터 필요 -> collect_market.py --init --years 5 먼저 실행):
    python backtest_dynamic.py                 # K=0.8, 상위 50
    python backtest_dynamic.py --k 0.5 --top 30
    python backtest_dynamic.py --start 20230101 --end 20250101
    python backtest_dynamic.py --no-cost
"""
import argparse

import pandas as pd

import db
from backtest import FEE_RATE, SLIPPAGE_RATE, TAX_RATE, VOL_WINDOW, _load_market_regime

INDEX_CODE = "KS11"
MIN_PRICE = 1000


def _selection_by_date(top_n: int) -> pd.DataFrame:
    """거래일별 거래대금 상위 top_n 종목 (그날 '선발'되어 다음 거래일에 감시됨)."""
    query = """
    SELECT date, stock_code FROM (
        SELECT date, stock_code,
               ROW_NUMBER() OVER (
                   PARTITION BY date
                   ORDER BY CAST(close AS REAL) * volume DESC
               ) AS rn
        FROM daily_candles
        WHERE stock_code != ? AND close >= ?
    )
    WHERE rn <= ?
    """
    with db.get_connection() as conn:
        return pd.read_sql_query(query, conn, params=(INDEX_CODE, MIN_PRICE, top_n))


def _stock_trades(stock_code: str, k: float, selected_dates: set,
                  regime: dict, use_cost: bool) -> pd.DataFrame | None:
    """종목 하나의 (거래일, 수익률) 목록. 전일에 선발된 날만 진입 대상."""
    df = db.get_daily_candles_df(stock_code)
    if len(df) < VOL_WINDOW + 10:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    df["prev_range"] = (df["high"] - df["low"]).shift(1)
    df["target"] = df["open"] + k * df["prev_range"]

    # 전일에 거래대금 상위로 선발된 날만 감시 (실운영과 동일)
    df["allowed"] = df["date"].shift(1).isin(selected_dates)

    # 거래량 필터 (전일 거래량 > 20일 평균)
    prev_vol = df["volume"].shift(1)
    vol_ma = df["volume"].rolling(VOL_WINDOW).mean().shift(1)
    df["allowed"] &= prev_vol > vol_ma

    # 시장 필터
    df["allowed"] &= df["date"].map(lambda d: bool(regime.get(d, False)))

    # 익일시가 청산
    df["exit_price"] = df["open"].shift(-1)
    df = df.dropna().reset_index(drop=True)

    hit = (df["high"] >= df["target"]) & df["allowed"]
    if not hit.any():
        return None

    slippage = SLIPPAGE_RATE if use_cost else 0.0
    cost = (FEE_RATE * 2 + TAX_RATE) if use_cost else 0.0

    buy_price = df.loc[hit, "target"] * (1 + slippage)
    sell_price = df.loc[hit, "exit_price"]
    returns = (sell_price / buy_price) * (1 - cost) - 1

    return pd.DataFrame({"date": df.loc[hit, "date"].values, "ret": returns.values,
                         "stock_code": stock_code})


def run_dynamic(k: float = 0.8, top_n: int = 50,
                start_date: str | None = None, end_date: str | None = None,
                use_cost: bool = True) -> dict | None:
    selection = _selection_by_date(top_n)
    if selection.empty:
        return None

    regime = _load_market_regime()

    # 종목별 선발일 집합
    sel_by_stock: dict[str, set] = {}
    for code, grp in selection.groupby("stock_code"):
        sel_by_stock[code] = set(grp["date"])

    all_trades = []
    for code, sel_dates in sel_by_stock.items():
        trades = _stock_trades(code, k, sel_dates, regime, use_cost)
        if trades is not None:
            all_trades.append(trades)

    if not all_trades:
        return None

    trades = pd.concat(all_trades, ignore_index=True)
    if start_date:
        trades = trades[trades["date"] >= start_date]
    if end_date:
        trades = trades[trades["date"] <= end_date]
    if trades.empty:
        return None

    # 하루에 돌파된 종목 전체에 균등 배분했다고 가정 -> 일별 수익률 = 그날 거래 평균
    daily = trades.groupby("date")["ret"].mean().sort_index()
    equity = (1 + daily).cumprod()
    peak = equity.cummax()
    mdd = (equity / peak - 1).min()

    return {
        "k": k,
        "top_n": top_n,
        "period": f"{daily.index[0]}~{daily.index[-1]}",
        "trades": len(trades),
        "trade_days": len(daily),
        "win_rate": (trades["ret"] > 0).mean(),
        "avg_trade_return": trades["ret"].mean(),
        "cum_return": equity.iloc[-1] - 1,
        "mdd": mdd,
        "stocks_traded": trades["stock_code"].nunique(),
    }


def _fmt(r: dict) -> str:
    return (f"K={r['k']:.1f} TOP{r['top_n']} | 기간 {r['period']} | "
            f"거래 {r['trades']}건/{r['trade_days']}일/{r['stocks_traded']}종목 | "
            f"승률 {r['win_rate']:.1%} | 거래당 {r['avg_trade_return']:.3%} | "
            f"누적 {r['cum_return']:.1%} | MDD {r['mdd']:.1%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="동적 유니버스 변동성 돌파 백테스트")
    parser.add_argument("--k", type=float, default=0.8)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    parser.add_argument("--no-cost", action="store_true")
    parser.add_argument("--sweep", action="store_true", help="K 0.3~0.9 스캔")
    args = parser.parse_args()

    db.init_db()

    if args.sweep:
        for k10 in range(3, 10):
            r = run_dynamic(k=k10 / 10, top_n=args.top,
                            start_date=args.start, end_date=args.end,
                            use_cost=not args.no_cost)
            print(_fmt(r) if r else f"K={k10/10:.1f}: 거래 없음")
    else:
        r = run_dynamic(k=args.k, top_n=args.top,
                        start_date=args.start, end_date=args.end,
                        use_cost=not args.no_cost)
        if r is None:
            print("데이터가 없습니다. collect_market.py --init --years 5 를 먼저 실행하세요.")
        else:
            print(_fmt(r))
