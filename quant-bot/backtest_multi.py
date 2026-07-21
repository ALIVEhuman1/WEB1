"""여러 매매법 백테스트 + 멀티 전략 포트폴리오 검증 (일봉 기반).

전략 (동일 비용 모델: 수수료 0.015%x2 + 거래세 0.18% + 슬리피지 0.1%):
- breakout   변동성 돌파: 기존 확정 규칙 (K=0.8, 거래량/시장 필터, 익일시가 청산), 고정 watchlist
- index      지수 타이밍(절대 모멘텀): 코스피 종가 > 200일선이면 지수 보유, 아니면 현금
- lowvol      저변동성 우량주 (2026-07 검증 통과: 거래당 +1.57%, 승률 56%, MDD -20.7%,
              하락장에도 시장 -35% 대비 -8.9%로 방어. 방어형 세 번째 전략 후보)
- overnight   오버나잇 프리미엄 (2026-07 검증 탈락: 4구간 전부 거래당 -. 엣지는 있으나 매일
              왕복비용 0.41%에 소멸. breakout이 신호 때만 밤샘 보유하는 이유 -> 참고용)
- turnofmonth 월말·월초 효과 (2026-07 검증 탈락: 효과 미약, 하락장 -0.27%/횡보 ~0/상승만 +,
              60거래로 표본 부족 -> 참고용)
- recover    대장주 회복 재진입 (2026-07 검증 탈락: 목표였던 하락장 21-22에서 거래당 -2.17%,
             누적 -97%, MDD -97%. 가짜 회복/데드캣 바운스마다 잘림. 높은 누적은 복리 아티팩트
             + 승률 23% 복권형. 롱온리로 폭락장 정답은 현금 -> 참고용)
- relstr     상대강도 스윙 (2026-07 검증 탈락: 하락장 거래당 -1.87%, 누적 -92%. recover와 0.85
             상관 = 사실상 동일. '버티는 종목' 직관도 폭락장엔 안 통함이 실측됨 -> 참고용)
- gapdown    갭 하락 반등 (2026-07 검증 탈락: 거래당 -0.44%, 하락장에서만 +0.26% -> 참고용)
- meanrev    평균회귀 (2026-07 검증 탈락 -> 참고용)
- trend      5/20 골든크로스 (2026-07 검증 탈락 -> 참고용)
- momentum   횡단면 모멘텀 (2026-07 검증 탈락: 한국시장 모멘텀 부진 문헌과 일치 -> 참고용)
- high52     52주 신고가 (2026-07 검증 탈락 -> 참고용)

성능: 전 종목 데이터는 한 번만 로드해 모든 전략이 공유하고, 계산도 한 번만 한 뒤
기간별로 잘라서 요약한다. --split 하나로 전체/하락장/횡보장/상승장 4개 표가 나온다.

사용법:
    python backtest_multi.py --split                  # 표준 4개 구간 한 번에 (권장)
    python backtest_multi.py                          # 전체 기간만
    python backtest_multi.py --start 20250101         # 구간 지정
    python backtest_multi.py --strategies momentum,index
    python backtest_multi.py --split --strategies breakout,index,recover,relstr  # 스윙 검증
    python backtest_multi.py --split --strategies breakout,index,lowvol,overnight,turnofmonth
"""
import argparse

import numpy as np
import pandas as pd

import db
from backtest import FEE_RATE, SLIPPAGE_RATE, TAX_RATE

INDEX_CODE = "KS11"
MIN_TURNOVER = 1_000_000_000  # 유동성 필터: 60일 평균 거래대금 10억원
ROUND_TRIP_COST = FEE_RATE * 2 + TAX_RATE

SPLIT_WINDOWS = [
    ("전체", None, None),
    ("하락장 21-22", None, "20230101"),
    ("횡보장 23-24", "20230101", "20250101"),
    ("상승장 25-26", "20250101", None),
]


def _all_stock_codes() -> list[str]:
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT stock_code FROM daily_candles WHERE stock_code != ?", (INDEX_CODE,)
        ).fetchall()
    return [r[0] for r in rows]


def _arrays(df: pd.DataFrame) -> dict:
    """전략 계산에 쓰는 numpy 배열 모음 (파이썬 루프에서 pandas 스칼라 접근은 매우 느림)."""
    c = df["close"].astype(float)
    return {
        "dates": df["date"].to_numpy(),
        "o": df["open"].astype(float).to_numpy(),
        "c": c.to_numpy(),
        "ma5": c.rolling(5).mean().to_numpy(),
        "ma20": c.rolling(20).mean().to_numpy(),
        "ma60": c.rolling(60).mean().to_numpy(),
        "ma200": c.rolling(200).mean().to_numpy(),
        "hi252": c.shift(1).rolling(252).max().to_numpy(),
        # 낙폭 판정용 (오늘 포함 후행 창, 미래 참조 없음)
        "roll_hi252": c.rolling(252, min_periods=120).max().to_numpy(),
        "roll_lo60": c.rolling(60, min_periods=40).min().to_numpy(),
        "turnover_ma": (c * df["volume"]).rolling(60).mean().to_numpy(),
    }


def meanrev_trades(a: dict) -> list[dict]:
    """3일 연속 하락 & 200일선 위 -> 종가 매수, 5일선 회복 or 5일 후 종가 매도."""
    c, ma5 = a["c"], a["ma5"]
    n = len(c)
    down3 = np.zeros(n, dtype=bool)
    down3[3:] = (c[3:] < c[2:-1]) & (c[2:-1] < c[1:-2]) & (c[1:-2] < c[:-3])
    with np.errstate(invalid="ignore"):
        signal = down3 & (c > a["ma200"]) & (a["turnover_ma"] > MIN_TURNOVER)

    trades, i = [], 0
    for t in np.nonzero(signal)[0]:
        if t < i or t + 1 >= n:
            continue
        entry = c[t] * (1 + SLIPPAGE_RATE)
        exit_i = min(t + 5, n - 1)
        for u in range(t + 1, min(t + 6, n)):
            if c[u] > ma5[u]:
                exit_i = u
                break
        ret = (c[exit_i] / entry) * (1 - ROUND_TRIP_COST) - 1
        trades.append({"date": a["dates"][exit_i], "ret": ret, "hold": int(exit_i - t)})
        i = exit_i + 1
    return trades


def _hold_until(a: dict, entry_signal: np.ndarray, exit_signal: np.ndarray, start: int) -> list[dict]:
    """공통 루프: 신호일 익일 시가 매수 -> 청산 신호일 익일 시가 매도."""
    o, dates = a["o"], a["dates"]
    n = len(o)
    trades, holding_from, entry_price = [], None, 0.0
    for t in range(start, n - 1):
        if holding_from is None:
            if entry_signal[t]:
                holding_from = t + 1
                entry_price = o[t + 1] * (1 + SLIPPAGE_RATE)
        elif exit_signal[t]:
            ret = (o[t + 1] / entry_price) * (1 - ROUND_TRIP_COST) - 1
            trades.append({"date": dates[t + 1], "ret": ret, "hold": int(t + 1 - holding_from)})
            holding_from = None
    # 마지막 바까지 청산 안 된 포지션은 최종 시가로 마감 (진행 중인 스윙도 반영)
    if holding_from is not None:
        ret = (o[n - 1] / entry_price) * (1 - ROUND_TRIP_COST) - 1
        trades.append({"date": dates[n - 1], "ret": ret, "hold": int(n - 1 - holding_from)})
    return trades


def trend_trades(a: dict) -> list[dict]:
    """5일선이 20일선 상향돌파 -> 익일 시가 매수, 하향돌파 -> 익일 시가 매도."""
    ma5, ma20 = a["ma5"], a["ma20"]
    n = len(ma5)
    up = np.zeros(n, dtype=bool)
    dn = np.zeros(n, dtype=bool)
    with np.errstate(invalid="ignore"):
        up[1:] = (ma5[1:] > ma20[1:]) & (ma5[:-1] <= ma20[:-1])
        dn[1:] = (ma5[1:] < ma20[1:]) & (ma5[:-1] >= ma20[:-1])
        up &= a["turnover_ma"] > MIN_TURNOVER
    return _hold_until(a, up, dn, 21)


def high52_trades(a: dict) -> list[dict]:
    """종가가 직전 52주 최고가 돌파 -> 익일 시가 매수, 20일선 이탈 -> 익일 시가 매도."""
    with np.errstate(invalid="ignore"):
        entry = (a["c"] > a["hi252"]) & (a["turnover_ma"] > MIN_TURNOVER)
        exit_ = a["c"] < a["ma20"]
    return _hold_until(a, entry, exit_, 253)


GAPDOWN_THRESHOLD = 0.97  # 전일 종가 대비 -3% 이상 갭 하락


def gapdown_trades(a: dict) -> list[dict]:
    """200일선 위 종목이 -3% 이상 갭 하락 출발 -> 시가 매수, 당일 종가 매도.

    판단에 쓰는 정보(전일 종가/전일 MA200/전일 거래대금)는 모두 개장 시점에
    알 수 있는 것들이라 미래 참조가 없다.
    """
    o, c = a["o"], a["c"]
    with np.errstate(invalid="ignore"):
        sig = (o[1:] <= c[:-1] * GAPDOWN_THRESHOLD) \
            & (c[:-1] > a["ma200"][:-1]) \
            & (a["turnover_ma"][:-1] > MIN_TURNOVER)
    entry = o[1:][sig] * (1 + SLIPPAGE_RATE)
    rets = (c[1:][sig] / entry) * (1 - ROUND_TRIP_COST) - 1
    dates = a["dates"][1:][sig]
    return [{"date": d, "ret": float(r), "hold": 1} for d, r in zip(dates, rets)]


RECOVER_DRAWDOWN = 0.80   # 최근 고점 대비 -20% 이상 빠졌던 종목만 (딥밸류 조건)


def recover_trades(a: dict) -> list[dict]:
    """대장주 회복 재진입: 깊게 빠졌던 종목이 60일선을 다시 상향 돌파 -> 익일 시가 매수,
    60일선 이탈 -> 익일 시가 매도 (수개월 스윙). 칼날 잡지 않고 회복 확인 후 진입.

    조건(모두 후행 데이터, 미래 참조 없음):
    - 60일선 상향 돌파 (회복 신호)
    - 최근 60일 최저가가 최근 252일 최고가의 80% 이하 (실제로 -20%+ 급락했던 종목)
    - 유동성 필터
    """
    c, ma60 = a["c"], a["ma60"]
    n = len(c)
    up = np.zeros(n, dtype=bool)
    with np.errstate(invalid="ignore"):
        up[1:] = (c[1:] > ma60[1:]) & (c[:-1] <= ma60[:-1])
        deep = a["roll_lo60"] <= RECOVER_DRAWDOWN * a["roll_hi252"]
        entry = up & deep & (a["turnover_ma"] > MIN_TURNOVER)
        exit_ = c < ma60
    return _hold_until(a, entry, exit_, 120)


def relstr_trades(a: dict, idx_ret: dict, idx_weak: dict) -> list[dict]:
    """상대강도 스윙(대조군, 회원님 '버티는 종목' 아이디어): 약세장(코스피<20일선)에서
    자기 60일선 위 & 60일 수익률이 코스피보다 높은 종목 매수, 60일선 이탈 시 매도.
    """
    c, ma60, dates = a["c"], a["ma60"], a["dates"]
    n = len(c)
    stock_ret60 = np.full(n, np.nan)
    stock_ret60[60:] = c[60:] / c[:-60] - 1
    entry = np.zeros(n, dtype=bool)
    with np.errstate(invalid="ignore"):
        for t in range(60, n - 1):
            if not idx_weak.get(dates[t], False):
                continue
            ir = idx_ret.get(dates[t])
            if ir is None or np.isnan(stock_ret60[t]):
                continue
            if c[t] > ma60[t] and stock_ret60[t] > ir:   # 지수보다 강하고 자기 추세 유지
                entry[t] = True
        exit_ = c < ma60
    return _hold_until(a, entry, exit_, 60)


def overnight_trades(a: dict) -> list[dict]:
    """오버나잇 프리미엄: 매 거래일 종가 매수 -> 익일 시가 매도 (밤새 보유).
    breakout의 진짜 수익원(익일시가 청산)을 순수하게 떼어내 검증. 유동성 필터 적용.
    """
    o, c, dates = a["o"], a["c"], a["dates"]
    entry = c[:-1] * (1 + SLIPPAGE_RATE)
    ret = (o[1:] / entry) * (1 - ROUND_TRIP_COST) - 1
    with np.errstate(invalid="ignore"):
        ok = a["turnover_ma"][:-1] > MIN_TURNOVER
    return [{"date": d, "ret": float(r), "hold": 1}
            for d, r in zip(dates[1:][ok], ret[ok])]


MOMENTUM_TOP_N = 20
MOMENTUM_LOOKBACK = 126  # 약 6개월


def momentum_series(panel: pd.DataFrame, to_panel: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """매월 말 6개월 수익률 상위 20종목 매수, 다음 달 보유. (일별 수익률, 거래 목록)."""
    rets = panel.pct_change()

    dates = panel.index.to_list()
    date_pos = {d: i for i, d in enumerate(dates)}
    month_ends = [dates[i] for i in range(len(dates) - 1) if dates[i][:6] != dates[i + 1][:6]]

    daily_parts, trade_rows = [], []
    prev_holdings: set = set()
    for mi, me in enumerate(month_ends):
        i = date_pos[me]
        if i < MOMENTUM_LOOKBACK:
            continue
        mom = (panel.loc[me] / panel.iloc[i - MOMENTUM_LOOKBACK] - 1).where(to_panel.loc[me] > MIN_TURNOVER)
        top = set(mom.dropna().nlargest(MOMENTUM_TOP_N).index)
        if not top:
            continue

        next_me_i = date_pos[month_ends[mi + 1]] if mi + 1 < len(month_ends) else len(dates) - 1
        hold_dates = dates[i + 1:next_me_i + 1]
        if not hold_dates:
            continue

        block = rets.loc[hold_dates, list(top)].mean(axis=1)
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


LOWVOL_TOP_N = 10        # 워치리스트 50종목 중 최저변동성 10종목
LOWVOL_LOOKBACK = 60     # 변동성 측정 창 (약 3개월)


def _watchlist_panel() -> pd.DataFrame:
    """워치리스트 종가를 코스피 거래일 캘린더에 정렬한 패널 (lowvol용, ~소용량)."""
    from main import load_watchlist

    cal = [r["date"] for r in db.get_daily_candles(INDEX_CODE)]
    if not cal:
        raise RuntimeError("lowvol 전략은 코스피(KS11) 데이터가 필요합니다. collect_history_fdr.py 먼저 실행.")
    date_pos = {d: i for i, d in enumerate(cal)}
    cols, codes = [], []
    for code in load_watchlist():
        df = db.get_daily_candles_df(code)
        if len(df) < LOWVOL_LOOKBACK + 20:
            continue
        df = df.sort_values("date").reset_index(drop=True)
        pos = np.fromiter((date_pos.get(d, -1) for d in df["date"].to_numpy()), dtype=np.int64)
        mask = pos >= 0
        col = np.full(len(cal), np.nan, dtype=np.float32)
        col[pos[mask]] = df["close"].astype(float).to_numpy()[mask]
        cols.append(col)
        codes.append(code)
    return pd.DataFrame(np.column_stack(cols), index=cal, columns=codes)


def lowvol_series(panel: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """매월 말 최근 변동성이 가장 낮은 N종목 매수, 다음 달 보유 (저변동성 이상현상)."""
    rets = panel.pct_change()
    vol = rets.rolling(LOWVOL_LOOKBACK).std()
    dates = panel.index.to_list()
    date_pos = {d: i for i, d in enumerate(dates)}
    month_ends = [dates[i] for i in range(len(dates) - 1) if dates[i][:6] != dates[i + 1][:6]]

    daily_parts, trade_rows, prev = [], [], set()
    for mi, me in enumerate(month_ends):
        i = date_pos[me]
        if i < LOWVOL_LOOKBACK:
            continue
        v = vol.loc[me].dropna()
        if v.empty:
            continue
        low = set(v.nsmallest(LOWVOL_TOP_N).index)
        next_i = date_pos[month_ends[mi + 1]] if mi + 1 < len(month_ends) else len(dates) - 1
        hold_dates = dates[i + 1:next_i + 1]
        if not hold_dates:
            continue
        block = rets.loc[hold_dates, list(low)].mean(axis=1)
        block.iloc[0] -= (len(low - prev) / len(low)) * (ROUND_TRIP_COST + SLIPPAGE_RATE)
        daily_parts.append(block)
        for code in low:
            entry, exit_ = panel.loc[me, code], panel.loc[hold_dates[-1], code]
            if pd.notna(entry) and pd.notna(exit_):
                cost = (ROUND_TRIP_COST + SLIPPAGE_RATE) if code not in prev else 0.0
                trade_rows.append({"date": hold_dates[-1], "ret": exit_ / entry - 1 - cost,
                                   "hold": len(hold_dates)})
        prev = low
    daily = pd.concat(daily_parts).fillna(0.0) if daily_parts else pd.Series(dtype=float)
    return daily, pd.DataFrame(trade_rows)


INDEX_SWITCH_COST = 0.0015  # ETF 왕복 비용 가정 (거래세 없음)


def index_series() -> tuple[pd.Series, pd.DataFrame]:
    """코스피 종가 > 200일선이면 보유, 아니면 현금 (절대 모멘텀, ETF 추종 가정)."""
    df = db.get_daily_candles_df(INDEX_CODE).sort_values("date").reset_index(drop=True)
    c = df["close"].astype(float)
    ma200 = c.rolling(200).mean()
    pos = (c > ma200).shift(1, fill_value=False)
    ret = c.pct_change().fillna(0.0) * pos
    switch = pos != pos.shift(1, fill_value=False)
    ret[switch] -= INDEX_SWITCH_COST / 2

    daily = pd.Series(ret.values, index=df["date"].values)

    trade_rows, entry_i = [], None
    cv = c.to_numpy()
    for t in range(len(df)):
        if pos[t] and entry_i is None:
            entry_i = t
        elif not pos[t] and entry_i is not None:
            trade_rows.append({"date": df["date"][t - 1],
                               "ret": cv[t - 1] / cv[entry_i] - 1 - INDEX_SWITCH_COST,
                               "hold": t - entry_i})
            entry_i = None
    if entry_i is not None:
        trade_rows.append({"date": df["date"].iloc[-1],
                           "ret": cv[-1] / cv[entry_i] - 1 - INDEX_SWITCH_COST,
                           "hold": len(df) - entry_i})
    return daily, pd.DataFrame(trade_rows)


TOM_HOLD = 4  # 월말 마지막 거래일 매수 후 보유할 거래일 수 (월말 + 초반 며칠)


def turnofmonth_trades() -> pd.DataFrame:
    """월말·월초 효과: 매월 마지막 거래일 종가에 코스피 ETF 매수, TOM_HOLD 거래일 뒤 매도."""
    df = db.get_daily_candles_df(INDEX_CODE).sort_values("date").reset_index(drop=True)
    dates = df["date"].to_list()
    c = df["close"].astype(float).to_numpy()
    n = len(dates)
    month_ends = [i for i in range(n - 1) if dates[i][:6] != dates[i + 1][:6]]
    rows = []
    for i in month_ends:
        exit_i = min(i + TOM_HOLD, n - 1)
        if exit_i <= i:
            continue
        ret = c[exit_i] / c[i] - 1 - INDEX_SWITCH_COST
        rows.append({"date": dates[exit_i], "ret": float(ret), "hold": exit_i - i})
    return pd.DataFrame(rows)


def _breakout_daily_trades() -> pd.DataFrame:
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


def _index_return_map(window: int = 60) -> tuple[dict, dict]:
    """코스피 60일 수익률 맵과 약세장(종가<20일선) 여부 맵. relstr 전략용."""
    df = db.get_daily_candles_df(INDEX_CODE).sort_values("date").reset_index(drop=True)
    c = df["close"].astype(float)
    ret = (c / c.shift(window) - 1)
    weak = (c < c.rolling(20).mean())
    return (dict(zip(df["date"], ret)), dict(zip(df["date"], weak)))


def _watchlist_trades(kind: str) -> pd.DataFrame:
    """대장주 워치리스트(50종목)에 recover/relstr 전략을 적용한 거래 목록."""
    from main import load_watchlist

    idx_ret, idx_weak = _index_return_map() if kind == "relstr" else ({}, {})
    rows = []
    for code in load_watchlist():
        df = db.get_daily_candles_df(code)
        if len(df) < 130:
            continue
        df = df.sort_values("date").reset_index(drop=True)
        a = _arrays(df)
        if kind == "recover":
            rows.extend(recover_trades(a))
        elif kind == "overnight":
            rows.extend(overnight_trades(a))
        else:
            rows.extend(relstr_trades(a, idx_ret, idx_weak))
    return pd.DataFrame(rows)


PER_STOCK_STRATEGIES = {"meanrev": meanrev_trades, "trend": trend_trades,
                        "high52": high52_trades, "gapdown": gapdown_trades}


def compute_all(names: list[str]) -> dict[str, tuple[pd.Series | None, pd.DataFrame]]:
    """전 종목 데이터를 한 번만 로드해 요청된 모든 전략을 계산한다.

    메모리 절약(e2-micro 1GB 대응): momentum 패널은 종목별 pandas 객체를 쌓지 않고,
    코스피 지수의 거래일 캘린더에 정렬된 float32 배열로 만든다 (~25MB 수준).
    """
    results: dict = {}
    per_stock = [n for n in names if n in PER_STOCK_STRATEGIES]
    need_panel = "momentum" in names

    if per_stock or need_panel:
        acc = {n: [] for n in per_stock}
        if need_panel:
            cal = [r["date"] for r in db.get_daily_candles(INDEX_CODE)]
            if not cal:
                raise RuntimeError("momentum 전략은 코스피 지수(KS11) 데이터가 필요합니다. collect_history_fdr.py를 먼저 실행하세요.")
            date_pos = {d: i for i, d in enumerate(cal)}
            close_cols, to_cols, panel_codes = [], [], []

        codes = _all_stock_codes()
        for k, code in enumerate(codes, 1):
            df = db.get_daily_candles_df(code)
            if len(df) < 220:
                continue
            df = df.sort_values("date").reset_index(drop=True)
            a = _arrays(df)
            for n in per_stock:
                acc[n].extend(PER_STOCK_STRATEGIES[n](a))
            if need_panel and len(df) >= 300:
                pos = np.fromiter((date_pos.get(d, -1) for d in a["dates"]), dtype=np.int64)
                mask = pos >= 0
                cvec = np.full(len(cal), np.nan, dtype=np.float32)
                tvec = np.full(len(cal), np.nan, dtype=np.float32)
                cvec[pos[mask]] = a["c"][mask]
                tvec[pos[mask]] = a["turnover_ma"][mask]
                close_cols.append(cvec)
                to_cols.append(tvec)
                panel_codes.append(code)
            if k % 500 == 0:
                print(f"  ... 종목 로드/계산 {k}/{len(codes)}")

        for n in per_stock:
            results[n] = (None, pd.DataFrame(acc[n]))
        if need_panel:
            panel = pd.DataFrame(np.column_stack(close_cols), index=cal, columns=panel_codes)
            to_panel = pd.DataFrame(np.column_stack(to_cols), index=cal, columns=panel_codes)
            del close_cols, to_cols
            results["momentum"] = momentum_series(panel, to_panel)

    if "breakout" in names:
        results["breakout"] = (None, _breakout_daily_trades())
    if "index" in names:
        results["index"] = index_series()
    if "recover" in names:
        results["recover"] = (None, _watchlist_trades("recover"))
    if "relstr" in names:
        results["relstr"] = (None, _watchlist_trades("relstr"))
    if "overnight" in names:
        results["overnight"] = (None, _watchlist_trades("overnight"))
    if "lowvol" in names:
        results["lowvol"] = lowvol_series(_watchlist_panel())
    if "turnofmonth" in names:
        results["turnofmonth"] = (None, turnofmonth_trades())
    return results


def summarize(name: str, daily: pd.Series | None, trades: pd.DataFrame,
              start_date: str | None, end_date: str | None) -> tuple[pd.Series, dict] | None:
    if trades.empty:
        return None
    t = trades
    if start_date:
        t = t[t["date"] >= start_date]
    if end_date:
        t = t[t["date"] <= end_date]
    if t.empty:
        return None

    if daily is None:
        d = t.groupby("date")["ret"].mean().sort_index()
    else:
        d = daily
        if start_date:
            d = d[d.index >= start_date]
        if end_date:
            d = d[d.index <= end_date]
        if d.empty:
            return None

    equity = (1 + d).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    return d, {
        "strategy": name,
        "trades": len(t),
        "win_rate": (t["ret"] > 0).mean(),
        "avg_trade_return": t["ret"].mean(),
        "avg_hold_days": t["hold"].mean(),
        "cum_return": equity.iloc[-1] - 1,
        "mdd": mdd,
    }


def combine(dailies: dict[str, pd.Series]) -> dict:
    aligned = pd.DataFrame(dailies).fillna(0.0).sort_index()
    combined = aligned.mean(axis=1)
    equity = (1 + combined).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    return {"cum_return": equity.iloc[-1] - 1, "mdd": mdd, "correlation": aligned.corr()}


def _fmt(s: dict) -> str:
    return (f"{s['strategy']:>9} | 거래 {s['trades']:5d}건 | 승률 {s['win_rate']:.1%} | "
            f"거래당 {s['avg_trade_return']:+.3%} | 평균보유 {s['avg_hold_days']:.1f}일 | "
            f"누적 {s['cum_return']:+.1%} | MDD {s['mdd']:.1%}")


def report_window(label: str, computed: dict, start: str | None, end: str | None) -> None:
    print(f"\n===== {label} ({start or '처음'} ~ {end or '현재'}) =====")
    dailies = {}
    for name, (daily, trades) in computed.items():
        r = summarize(name, daily, trades, start, end)
        if r is None:
            print(f"{name:>9} | 거래 없음")
            continue
        dailies[name] = r[0]
        print(_fmt(r[1]))
    if len(dailies) >= 2:
        c = combine(dailies)
        print(f"[결합(균등배분)] 누적 {c['cum_return']:+.1%} | MDD {c['mdd']:.1%}")
        print("상관관계:")
        print(c["correlation"].round(2).to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="멀티 전략 백테스트")
    parser.add_argument("--strategies", type=str, default="breakout,index")
    parser.add_argument("--split", action="store_true", help="전체/하락/횡보/상승 4개 구간을 한 번에 출력")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    args = parser.parse_args()

    db.init_db()
    names = [s.strip() for s in args.strategies.split(",")]
    print(f"전략 계산 중 (1회만 수행): {', '.join(names)}")
    computed = compute_all(names)

    if args.split:
        for label, s, e in SPLIT_WINDOWS:
            report_window(label, computed, s, e)
    else:
        report_window("결과", computed, args.start, args.end)
