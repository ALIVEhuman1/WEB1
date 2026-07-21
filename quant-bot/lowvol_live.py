"""저변동성 우량주 월간 리밸런싱 전략 (2026-07 백테스트 통과, 방어형).

매월 첫 거래일에 워치리스트 대형주 중 최근 60일 일간수익률 변동성이 가장 낮은
LOWVOL_TOP_N 종목으로 교체 보유한다. 저변동성 이상현상에 기반하며, 하락장에서
손실을 크게 줄이는 방어 성격이 있다 (백테스트: 시장 -35% 구간에 -8.9%).

.env의 LOWVOL_BUDGET_KRW가 0이면 비활성 (opt-in). 돌파/지수 전략과 자본이 분리되고
positions.strategy='lowvol'로 구분되어, 아침 오버나잇 청산이나 돌파 슬롯에 영향을 주지 않는다.
"""
import json
import logging
import statistics
import time

import config
import db
import kis_order
from alerts import _post as discord_post

logger = logging.getLogger(__name__)

STRATEGY = "lowvol"
LOOKBACK = 60                                   # 변동성 측정 창 (백테스트와 동일)
STATE_PATH = config.BASE_DIR / "lowvol_state.json"
POLL_DELAY = 0.6                                # 모의서버 초당 호출 제한 대응


def _volatility(code: str) -> float | None:
    """최근 LOOKBACK일 일간수익률의 표준편차. 데이터 부족 시 None."""
    rows = db.get_daily_candles(code)
    if len(rows) < LOOKBACK + 1:
        return None
    closes = [r["close"] for r in rows[-(LOOKBACK + 1):]]
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(rets) < LOOKBACK // 2:
        return None
    return statistics.stdev(rets)


def select_targets() -> list[str]:
    """워치리스트에서 변동성이 가장 낮은 LOWVOL_TOP_N 종목 선정."""
    from main import load_watchlist

    vols = []
    for code in load_watchlist():
        v = _volatility(code)
        if v is not None:
            vols.append((v, code))
    vols.sort()
    return [code for _, code in vols[:config.LOWVOL_TOP_N]]


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            logger.warning("lowvol 상태 파일 파싱 실패, 새로 시작")
    return {}


def _save_state(month: str) -> None:
    STATE_PATH.write_text(json.dumps({"last_rebalance_month": month}))


def manage_position(access_token: str, today: str) -> str:
    """월 1회 리밸런싱. 이번 달에 이미 했으면 보유 유지. 수행한 행동 문자열 반환."""
    if config.LOWVOL_BUDGET_KRW <= 0:
        return "disabled"

    month = today[:6]
    if _load_state().get("last_rebalance_month") == month:
        return "hold"  # 이번 달 리밸런싱 완료됨

    targets = select_targets()
    if not targets:
        logger.warning("lowvol 대상 종목 선정 실패 (일봉 데이터 부족)")
        return "no-data"

    held = {p["stock_code"]: p for p in db.get_open_positions(STRATEGY)}
    target_set = set(targets)
    sells = [c for c in held if c not in target_set]
    buys = [c for c in targets if c not in held]
    per_stock_budget = config.LOWVOL_BUDGET_KRW // max(1, config.LOWVOL_TOP_N)

    for code in sells:  # 목표에서 빠진 종목 매도
        pos = held[code]
        try:
            kis_order.sell_market(access_token, code, pos["qty"])
            quote = kis_order.get_current_price(access_token, code)
            db.close_position(pos["id"], quote["price"], today)
            logger.info("lowvol 매도(리밸런싱 제외): %s x%d", code, pos["qty"])
        except Exception:
            logger.exception("lowvol %s 매도 실패 (다음 리밸런싱에서 재시도)", code)
        time.sleep(POLL_DELAY)

    for code in buys:   # 새로 편입된 종목 매수
        try:
            quote = kis_order.get_current_price(access_token, code)
            qty = per_stock_budget // quote["price"]
            if qty <= 0:
                logger.warning("lowvol %s: 예산(%d원) 대비 가격 높아 매수 불가", code, per_stock_budget)
                continue
            kis_order.buy_market(access_token, code, qty)
            db.add_position(code, qty, quote["price"], today, strategy=STRATEGY)
            logger.info("lowvol 매수(신규 편입): %s x%d @ %d", code, qty, quote["price"])
        except Exception:
            logger.exception("lowvol %s 매수 실패 (다음 리밸런싱에서 재시도)", code)
        time.sleep(POLL_DELAY)

    _save_state(month)
    kept = [c for c in targets if c in held]
    logger.info("=== lowvol 리밸런싱: 신규 %s / 제외 %s / 유지 %d종목 ===", buys or "없음", sells or "없음", len(kept))
    discord_post(f":shield: **[저변동성]** {month} 월간 리밸런싱: "
                 f"신규 {len(buys)}종목({', '.join(buys) if buys else '-'}) / "
                 f"제외 {len(sells)}종목 / 유지 {len(kept)}종목")
    return f"rebalanced(+{len(buys)}/-{len(sells)})"
