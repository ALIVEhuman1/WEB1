"""② 미국 신고가 돌파 추세추종 (돈치안 채널 + SPY 시장필터 + ATR 트레일링).

백테스트 검증(backtest_us_breakout.py)과 동일 규칙을 라이브 포지션 관리로 옮긴 것:
- 진입: SPY>200일선(시장필터) 통과 시, 종목이 100일 신고가(종가) 돌파 -> 매수.
        슬롯 경쟁 시 100일 모멘텀 강한 순.
- 청산: 진입 후 최고종가 - ATR×3 (샹들리에 트레일링) 이탈 시 매도. (손절/익절 통합)
- 트레일링 기준 peak는 저장된 일봉에서 매번 재구성 -> 상태 저장 없이 견고.

⚠️ 생존편향: 유니버스가 '오늘 살아남은 대형주'라 백테스트 절대수익은 과대평가.
   국면 행동(하락장 관망, 상승장 추세)은 유효하나 기대수익은 보수적으로.

US_BREAKOUT_BUDGET_USD가 0이면 드라이런(신호만 통보). 실돈은 예산>0 + 모의검증 후.
"""
import logging

import numpy as np
import pandas as pd

import config
import db
import kis_order_us
from alerts import _post as discord_post
from us_universe import load_us_universe

logger = logging.getLogger(__name__)

STRATEGY = "us_breakout"
DONCHIAN_ENTRY = 100
ATR_PERIOD = 20
ATR_MULT = 3.0
MOM_LOOKBACK = 100
SMA_LONG = 200
MIN_ROWS = SMA_LONG + 5   # 지표 계산 최소 일봉 수


def _load_df(symbol: str) -> pd.DataFrame | None:
    df = db.get_us_daily_candles_df(symbol)
    if df is None or len(df) < MIN_ROWS:
        return None
    return df


def market_ok() -> bool | None:
    """SPY 종가>200일선이면 True. 데이터 부족 시 None."""
    df = _load_df(config.US_INDEX_SYMBOL)
    if df is None:
        return None
    c = df["close"].astype(float)
    return bool(c.iloc[-1] > c.tail(SMA_LONG).mean())


def _atr(df: pd.DataFrame) -> float:
    """와일더 ATR(20)의 최신값."""
    h, low, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    prev = c.shift(1)
    tr = pd.concat([h - low, (h - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean().iloc[-1])


def entry_signal(symbol: str) -> dict | None:
    """오늘 100일 신고가 돌파면 {'mom': 모멘텀, 'close': 종가} 반환, 아니면 None."""
    df = _load_df(symbol)
    if df is None:
        return None
    c = df["close"].astype(float)
    donch_high = c.iloc[-(DONCHIAN_ENTRY + 1):-1].max()   # 오늘 제외 직전 100일 최고종가
    if np.isnan(donch_high) or c.iloc[-1] <= donch_high:
        return None
    mom = c.iloc[-1] / c.iloc[-1 - MOM_LOOKBACK] - 1 if len(c) > MOM_LOOKBACK else 0.0
    return {"mom": float(mom), "close": float(c.iloc[-1])}


def trail_broken(symbol: str, buy_date: str) -> bool | None:
    """진입 후 최고종가 - ATR×MULT 이탈이면 True(청산). 데이터 부족 시 None."""
    df = _load_df(symbol)
    if df is None:
        return None
    since = df[df.index >= buy_date]
    if since.empty:
        since = df.tail(1)
    peak = float(since["close"].astype(float).max())
    last = float(df["close"].astype(float).iloc[-1])
    return last < peak - ATR_MULT * _atr(df)


def _plan(open_positions: list[dict], mkt: bool) -> tuple[list[dict], list[str]]:
    """오늘의 청산·진입 계획을 세운다 (실주문 전 공통). 반환: (청산목록, 진입후보 심볼)."""
    exits = [p for p in open_positions if trail_broken(p["stock_code"], p["buy_date"])]
    held = {p["stock_code"] for p in open_positions}
    slots_free = config.US_BREAKOUT_MAX_POSITIONS - (len(open_positions) - len(exits))

    entries: list[str] = []
    if mkt and slots_free > 0:
        cands = []
        for sym in load_us_universe():
            if sym in held:
                continue
            sig = entry_signal(sym)
            if sig is not None:
                cands.append((sig["mom"], sym))
        cands.sort(reverse=True)   # 모멘텀 강한 순
        entries = [sym for _, sym in cands[:slots_free]]
    return exits, entries


def manage_position(access_token: str, today: str) -> str:
    """청산(트레일 이탈) 후 빈 슬롯만큼 신규 돌파 진입. 예산 0이면 드라이런(통보만)."""
    mkt = market_ok()
    if mkt is None:
        logger.warning("SPY 일봉 부족으로 시장필터 판단 불가 -> 신규 진입 보류(청산은 진행)")
    open_positions = db.get_open_positions(STRATEGY)
    exits, entries = _plan(open_positions, bool(mkt))
    budget = config.US_BREAKOUT_BUDGET_USD

    # 드라이런: 통보만
    if budget <= 0:
        filt = "위(진입가능)" if mkt else ("아래(관망)" if mkt is not None else "판단불가")
        discord_post(
            f":microscope: **[미장 돌파·드라이런]** SPY 200일선 {filt} | 보유 {len(open_positions)} | "
            f"청산예정 {len(exits)}건({', '.join(p['stock_code'] for p in exits) or '-'}) | "
            f"신규 {len(entries)}건({', '.join(entries) or '-'}) — 실주문 안 함")
        return "dryrun"

    # 1) 청산
    for pos in exits:
        try:
            quote = kis_order_us.get_current_price(access_token, pos["stock_code"])
            kis_order_us.sell_limit(access_token, pos["stock_code"], pos["qty"], quote["price"])
            db.close_position(pos["id"], quote["price"], today)
            ret = (quote["price"] / pos["buy_price"] - 1) * 100
            discord_post(f":arrow_down: **[미장 돌파]** {pos['stock_code']} 트레일 이탈 -> 매도 ({ret:+.2f}%)")
        except Exception:
            logger.exception("미장 돌파 청산 실패: %s", pos["stock_code"])

    # 2) 진입 (빈 슬롯만큼, 종목당 예산 = 총액 / 슬롯수)
    slot_budget = budget / max(config.US_BREAKOUT_MAX_POSITIONS, 1)
    bought = []
    for sym in entries:
        try:
            quote = kis_order_us.get_current_price(access_token, sym)
            qty = int(slot_budget // quote["price"])
            if qty <= 0:
                logger.warning("미장 돌파 슬롯예산 $%.2f로 %s 1주도 매수 불가 (현재가 $%.2f)",
                               slot_budget, sym, quote["price"])
                continue
            kis_order_us.buy_limit(access_token, sym, qty, quote["price"])
            db.add_position(sym, qty, quote["price"], today, strategy=STRATEGY)
            bought.append(sym)
            discord_post(f":arrow_up: **[미장 돌파]** {sym} 100일 신고가 돌파 -> {qty}주 매수 (~${quote['price']:.2f})")
        except Exception:
            logger.exception("미장 돌파 진입 실패: %s", sym)

    if not exits and not bought:
        return "hold" if open_positions else ("cash" if mkt else "wait")
    return f"exit{len(exits)}/buy{len(bought)}"
