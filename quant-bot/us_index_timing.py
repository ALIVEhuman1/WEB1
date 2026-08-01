"""① 미국 지수 타이밍(절대 모멘텀): SPY 종가 > 200일선이면 SPY 보유, 아니면 현금.

KR판 etf_timing.py의 미장 버전. 백테스트 검증(2005~, 5종목시뮬 아님 단일자산):
2008 금융위기 -23%->+0.9%, 2022 -18.6%->-16.2%로 하락장 MDD를 반토막 낸 '방패'.

신호는 db.us_daily_candles(사전에 us_data.py로 갱신)에서 계산 — 미래참조 없음.
US_INDEX_BUDGET_USD가 0이면 드라이런(신호만 통보, 실주문 X). 실돈은 예산>0 + 모의검증 후.
"""
import logging

import config
import db
import kis_order_us
from alerts import _post as discord_post

logger = logging.getLogger(__name__)

STRATEGY = "us_index"
MA_DAYS = 200


def desired_hold() -> bool | None:
    """저장된 SPY 일봉 기준 종가>200일선이면 True. 데이터 부족 시 None."""
    symbol = config.US_INDEX_SYMBOL
    rows = db.get_us_daily_candles(symbol)
    if len(rows) < MA_DAYS:
        logger.warning("%s 일봉 %d개뿐이라 200일선 판단 불가 (%d 필요)", symbol, len(rows), MA_DAYS)
        return None
    closes = [r["close"] for r in rows[-MA_DAYS:]]
    ma = sum(closes) / len(closes)
    latest = rows[-1]["close"]
    hold = latest > ma
    logger.info("미장 지수타이밍: %s %.2f vs MA%d %.2f -> %s", symbol, latest, MA_DAYS, ma,
                "보유" if hold else "현금")
    return hold


def manage_position(access_token: str, today: str) -> str:
    """목표 상태와 현재 보유를 비교해 매수/매도. 예산 0이면 드라이런(통보만)."""
    symbol = config.US_INDEX_SYMBOL
    desired = desired_hold()
    if desired is None:
        return "no-data"

    open_positions = db.get_open_positions(STRATEGY)
    budget = config.US_INDEX_BUDGET_USD

    # 드라이런: 실주문 없이 오늘 판단만 통보
    if budget <= 0:
        state = "보유(200일선 위)" if desired else "현금(200일선 아래)"
        discord_post(f":microscope: **[미장 지수타이밍·드라이런]** {symbol} 목표: {state} — 실주문 안 함 "
                     f"(현재 기록상 보유 {len(open_positions)}건)")
        return "dryrun"

    if desired and not open_positions:
        quote = kis_order_us.get_current_price(access_token, symbol)
        qty = int(budget // quote["price"])
        if qty <= 0:
            logger.warning("미장 지수 예산 $%.2f로 %s 1주도 매수 불가 (현재가 $%.2f)", budget, symbol, quote["price"])
            return "budget-too-small"
        kis_order_us.buy_limit(access_token, symbol, qty, quote["price"])
        db.add_position(symbol, qty, quote["price"], today, strategy=STRATEGY)
        logger.info("미장 지수 매수: %s x%d @~$%.2f (200일선 회복)", symbol, qty, quote["price"])
        discord_post(f":chart_with_upwards_trend: **[미장 지수타이밍]** {symbol} 200일선 회복 -> {qty}주 매수 (~${quote['price']:.2f})")
        return "bought"

    if not desired and open_positions:
        for pos in open_positions:
            quote = kis_order_us.get_current_price(access_token, pos["stock_code"])
            kis_order_us.sell_limit(access_token, pos["stock_code"], pos["qty"], quote["price"])
            db.close_position(pos["id"], quote["price"], today)
            ret = (quote["price"] / pos["buy_price"] - 1) * 100
            logger.info("미장 지수 매도: %s x%d (%.2f%%, 200일선 이탈)", pos["stock_code"], pos["qty"], ret)
            discord_post(f":shield: **[미장 지수타이밍]** {symbol} 200일선 이탈 -> 전량 매도 ({ret:+.2f}%)")
        return "sold"

    return "hold" if desired else "cash"
