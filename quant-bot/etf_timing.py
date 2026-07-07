"""지수 타이밍 전략 (절대 모멘텀): 코스피 종가 > 200일선이면 KODEX 200 보유, 아니면 현금.

백테스트 근거 (2026-07, 5년): 전체 +145%/MDD -23%, 하락장 전량 회피, 횡보장 -17%(휩쏘 비용).
변동성 돌파와 상관관계 0.21로 낮아 자본을 나눠 함께 운용한다 (positions.strategy='index').

.env의 ETF_BUDGET_KRW가 0이면 비활성 (opt-in).
"""
import logging

import config
import db
import kis_order
from alerts import _post as discord_post

logger = logging.getLogger(__name__)

ETF_CODE = "069500"   # KODEX 200
INDEX_CODE = "KS11"
MA_DAYS = 200
STRATEGY = "index"


def desired_hold() -> bool | None:
    """전일 기준 코스피 종가 > 200일 이동평균이면 True. 데이터 부족 시 None."""
    rows = db.get_daily_candles(INDEX_CODE)
    if len(rows) < MA_DAYS:
        logger.warning("지수 데이터 %d일분뿐이라 ETF 타이밍 판단 불가 (%d일 필요)", len(rows), MA_DAYS)
        return None
    closes = [r["close"] for r in rows[-MA_DAYS:]]
    ma = sum(closes) / len(closes)
    latest = rows[-1]["close"]
    hold = latest > ma
    logger.info("ETF 타이밍: 코스피 %s vs MA%d %.1f -> %s", latest, MA_DAYS, ma, "보유" if hold else "현금")
    return hold


def manage_position(access_token: str, today: str) -> str:
    """목표 상태와 현재 보유를 비교해 필요 시 매수/매도. 수행한 행동을 반환."""
    if config.ETF_BUDGET_KRW <= 0:
        return "disabled"

    desired = desired_hold()
    if desired is None:
        return "no-data"

    open_positions = db.get_open_positions(STRATEGY)

    if desired and not open_positions:
        quote = kis_order.get_current_price(access_token, ETF_CODE)
        qty = config.ETF_BUDGET_KRW // quote["price"]
        if qty <= 0:
            logger.warning("ETF 예산(%d원)으로 1주도 매수 불가 (현재가 %d)", config.ETF_BUDGET_KRW, quote["price"])
            return "budget-too-small"
        kis_order.buy_market(access_token, ETF_CODE, qty)
        db.add_position(ETF_CODE, qty, quote["price"], today, strategy=STRATEGY)
        logger.info("ETF 매수: %s x%d @ %d (코스피 200일선 상회)", ETF_CODE, qty, quote["price"])
        discord_post(f":chart_with_upwards_trend: **[지수 타이밍]** 코스피 200일선 회복 -> KODEX200 {qty}주 매수")
        return "bought"

    if not desired and open_positions:
        for pos in open_positions:
            kis_order.sell_market(access_token, pos["stock_code"], pos["qty"])
            quote = kis_order.get_current_price(access_token, pos["stock_code"])
            db.close_position(pos["id"], quote["price"], today)
            ret = (quote["price"] / pos["buy_price"] - 1) * 100
            logger.info("ETF 매도: %s x%d (수익률 %+.2f%%, 코스피 200일선 이탈)", pos["stock_code"], pos["qty"], ret)
            discord_post(f":shield: **[지수 타이밍]** 코스피 200일선 이탈 -> KODEX200 전량 매도 ({ret:+.2f}%)")
        return "sold"

    return "hold" if desired else "cash"
