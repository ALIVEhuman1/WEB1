"""변동성 돌파 전략 백테스트 (일봉 기반).

전략 (래리 윌리엄스 변동성 돌파 기본형):
- 돌파가격 = 당일 시가 + K * (전일 고가 - 전일 저가)
- 당일 고가가 돌파가격 이상이면 돌파가격에 매수했다고 가정
- 당일 종가에 매도 (오버나잇 없음)

일봉의 한계로 "돌파 후 종가까지"의 체결 순서는 알 수 없으므로,
고가 >= 돌파가격이면 돌파가격에 체결됐다고 가정한다 (보수적으로 슬리피지 반영).

옵션:
- --ma-filter: 전일 기준 5일 이동평균 > 20일 이동평균(상승 추세)인 날만 진입.
  노이즈 돌파를 걸러내는 가장 기본적인 필터. (전일 종가까지만 사용해 미래 참조 없음)
- --vol-filter: 전일 거래량이 20일 평균 거래량보다 큰 날만 진입.
  당일 거래량은 장중 진입 시점에 알 수 없으므로 전일 기준으로만 판단 (미래 참조 없음).
- --exit-open: 당일 종가 대신 다음날 시가에 매도 (오버나잇 보유).
  돌파 모멘텀이 다음날 아침까지 이어지는 경향을 활용하는 변형.
- --no-cost: 수수료/거래세/슬리피지를 0으로 놓고 전략의 순수 예측력만 진단.

사용법:
    python backtest.py                        # 전 종목, K=0.5
    python backtest.py --k 0.7               # K값 지정
    python backtest.py --sweep               # K 0.1~0.9 스캔
    python backtest.py --sweep --ma-filter   # 필터 적용 상태로 스캔
    python backtest.py --sweep --no-cost     # 비용 제외 진단
    python backtest.py --sweep --exit-open --vol-filter   # 조합 테스트
    python backtest.py --stock 005930        # 단일 종목
"""
import argparse

import pandas as pd

import db
from main import load_watchlist

FEE_RATE = 0.00015       # 매수/매도 수수료 (각각, 0.015%)
TAX_RATE = 0.0018        # 매도 시 증권거래세 (0.18%, 2025년 기준 코스피/코스닥)
SLIPPAGE_RATE = 0.001    # 슬리피지 가정 (0.1%)

MA_SHORT = 5
MA_LONG = 20
VOL_WINDOW = 20


def run_single(stock_code: str, k: float,
               start_date: str | None = None, end_date: str | None = None,
               use_cost: bool = True, ma_filter: bool = False,
               vol_filter: bool = False, exit_open: bool = False) -> dict | None:
    """단일 종목 백테스트. 데이터가 부족하면 None."""
    df = db.get_daily_candles_df(stock_code, start_date, end_date)
    if len(df) < MA_LONG + 10:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    df["prev_range"] = (df["high"] - df["low"]).shift(1)
    df["target"] = df["open"] + k * df["prev_range"]

    df["allowed"] = True
    if ma_filter:
        # 진입 판단은 당일 장중이므로, 이동평균은 전일 종가까지만 사용 (미래 참조 방지)
        ma_short = df["close"].rolling(MA_SHORT).mean().shift(1)
        ma_long = df["close"].rolling(MA_LONG).mean().shift(1)
        df["allowed"] &= ma_short > ma_long
    if vol_filter:
        # 당일 거래량은 진입 시점에 알 수 없으므로 전일 거래량 vs 20일 평균으로 판단
        prev_vol = df["volume"].shift(1)
        vol_ma = df["volume"].rolling(VOL_WINDOW).mean().shift(1)
        df["allowed"] &= prev_vol > vol_ma

    if exit_open:
        df["exit_price"] = df["open"].shift(-1)  # 다음날 시가 매도
    else:
        df["exit_price"] = df["close"]           # 당일 종가 매도

    df = df.dropna().reset_index(drop=True)

    # 돌파 발생일: 고가가 돌파가격 이상 (+ 필터 통과)
    hit = (df["high"] >= df["target"]) & df["allowed"]

    slippage = SLIPPAGE_RATE if use_cost else 0.0
    cost = (FEE_RATE * 2 + TAX_RATE) if use_cost else 0.0

    buy_price = df.loc[hit, "target"] * (1 + slippage)
    sell_price = df.loc[hit, "exit_price"]
    trade_returns = (sell_price / buy_price) * (1 - cost) - 1

    if trade_returns.empty:
        return None

    equity = (1 + trade_returns).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1

    wins = (trade_returns > 0).sum()
    return {
        "stock_code": stock_code,
        "trades": len(trade_returns),
        "win_rate": wins / len(trade_returns),
        "avg_return": trade_returns.mean(),
        "cum_return": equity.iloc[-1] - 1,
        "mdd": drawdown.min(),
        "period": f"{df['date'].iloc[0]}~{df['date'].iloc[-1]}",
    }


def run_all(k: float, watchlist: list[str] | None = None,
            start_date: str | None = None, end_date: str | None = None,
            use_cost: bool = True, ma_filter: bool = False,
            vol_filter: bool = False, exit_open: bool = False) -> pd.DataFrame:
    """watchlist 전 종목 백테스트 결과를 DataFrame으로 반환."""
    watchlist = watchlist if watchlist is not None else load_watchlist()
    results = []
    for code in watchlist:
        r = run_single(code, k, start_date, end_date, use_cost=use_cost, ma_filter=ma_filter,
                       vol_filter=vol_filter, exit_open=exit_open)
        if r:
            results.append(r)
    return pd.DataFrame(results)


def sweep_k(watchlist: list[str] | None = None,
            start_date: str | None = None, end_date: str | None = None,
            use_cost: bool = True, ma_filter: bool = False,
            vol_filter: bool = False, exit_open: bool = False) -> pd.DataFrame:
    """K값 0.1~0.9를 스캔해 K별 평균 성과를 비교한다."""
    watchlist = watchlist if watchlist is not None else load_watchlist()
    rows = []
    for k10 in range(1, 10):
        k = k10 / 10
        df = run_all(k, watchlist, start_date, end_date, use_cost=use_cost, ma_filter=ma_filter,
                     vol_filter=vol_filter, exit_open=exit_open)
        if df.empty:
            continue
        rows.append({
            "k": k,
            "stocks": len(df),
            "avg_trades": df["trades"].mean(),
            "avg_win_rate": df["win_rate"].mean(),
            "avg_trade_return": df["avg_return"].mean(),
            "avg_cum_return": df["cum_return"].mean(),
            "median_cum_return": df["cum_return"].median(),
            "avg_mdd": df["mdd"].mean(),
        })
    return pd.DataFrame(rows)


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _fmt_pct2(x: float) -> str:
    return f"{x * 100:.3f}%"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="변동성 돌파 백테스트")
    parser.add_argument("--k", type=float, default=0.5, help="돌파 계수 K (기본 0.5)")
    parser.add_argument("--stock", type=str, help="단일 종목코드만 테스트")
    parser.add_argument("--sweep", action="store_true", help="K 0.1~0.9 스캔")
    parser.add_argument("--start", type=str, help="시작일 YYYYMMDD")
    parser.add_argument("--end", type=str, help="종료일 YYYYMMDD")
    parser.add_argument("--no-cost", action="store_true", help="수수료/거래세/슬리피지 제외 (순수 전략 진단)")
    parser.add_argument("--ma-filter", action="store_true", help="5일MA > 20일MA(상승 추세)인 날만 진입")
    parser.add_argument("--vol-filter", action="store_true", help="전일 거래량 > 20일 평균인 날만 진입")
    parser.add_argument("--exit-open", action="store_true", help="당일 종가 대신 다음날 시가에 매도 (오버나잇)")
    args = parser.parse_args()

    db.init_db()
    pd.set_option("display.max_rows", 100)
    pd.set_option("display.width", 160)

    use_cost = not args.no_cost
    tags = []
    if args.no_cost:
        tags.append("비용 제외")
    if args.ma_filter:
        tags.append(f"MA{MA_SHORT}>MA{MA_LONG} 필터")
    if args.vol_filter:
        tags.append("거래량 필터")
    if args.exit_open:
        tags.append("익일시가 청산")
    tag_str = f" [{', '.join(tags)}]" if tags else ""

    if args.sweep:
        result = sweep_k(start_date=args.start, end_date=args.end,
                         use_cost=use_cost, ma_filter=args.ma_filter,
                         vol_filter=args.vol_filter, exit_open=args.exit_open)
        if result.empty:
            print("데이터가 없습니다. collect_history.py를 먼저 실행하세요.")
        else:
            print(f"K 스캔 결과{tag_str}")
            result["avg_win_rate"] = result["avg_win_rate"].map(_fmt_pct)
            result["avg_trade_return"] = result["avg_trade_return"].map(_fmt_pct2)
            result["avg_cum_return"] = result["avg_cum_return"].map(_fmt_pct)
            result["median_cum_return"] = result["median_cum_return"].map(_fmt_pct)
            result["avg_mdd"] = result["avg_mdd"].map(_fmt_pct)
            print(result.to_string(index=False))
    elif args.stock:
        r = run_single(args.stock, args.k, args.start, args.end,
                       use_cost=use_cost, ma_filter=args.ma_filter,
                       vol_filter=args.vol_filter, exit_open=args.exit_open)
        if r is None:
            print(f"{args.stock}: 데이터 부족 또는 거래 없음")
        else:
            print(f"종목: {r['stock_code']}  기간: {r['period']}{tag_str}")
            print(f"거래 수: {r['trades']}  승률: {_fmt_pct(r['win_rate'])}")
            print(f"평균 수익률: {_fmt_pct2(r['avg_return'])}  누적 수익률: {_fmt_pct(r['cum_return'])}  MDD: {_fmt_pct(r['mdd'])}")
    else:
        result = run_all(args.k, start_date=args.start, end_date=args.end,
                         use_cost=use_cost, ma_filter=args.ma_filter,
                         vol_filter=args.vol_filter, exit_open=args.exit_open)
        if result.empty:
            print("데이터가 없습니다. collect_history.py를 먼저 실행하세요.")
        else:
            result = result.sort_values("cum_return", ascending=False).reset_index(drop=True)
            display = result.copy()
            display["avg_return"] = display["avg_return"].map(_fmt_pct2)
            for col in ("win_rate", "cum_return", "mdd"):
                display[col] = display[col].map(_fmt_pct)
            print(display.to_string(index=False))
            print()
            print(f"[전체 요약] K={args.k}, 종목 {len(result)}개{tag_str}")
            print(f"평균 누적수익률: {_fmt_pct(result['cum_return'].mean())}  "
                  f"중앙값: {_fmt_pct(result['cum_return'].median())}  "
                  f"평균 승률: {_fmt_pct(result['win_rate'].mean())}  "
                  f"거래당 평균수익률: {_fmt_pct2(result['avg_return'].mean())}  "
                  f"평균 MDD: {_fmt_pct(result['mdd'].mean())}")
