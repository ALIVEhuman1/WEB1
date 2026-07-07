"""변동성 돌파 자동매매 (모의투자 전용으로 검증 후 실전 전환).

하루 흐름 (run_trading_day, 장 시작 전 실행 전제):
1. 일봉 데이터 최신화 (FDR, 전일봉까지 반영) 후 셋업 계산
2. 09:00 장 시작 대기
3. 오버나잇 포지션 전량 시장가 매도 (백테스트의 '익일 시가 청산')
4. 15:20까지 진입 후보 종목 가격 감시:
   돌파가격(시가 + K*전일변동폭) 도달 시 시장가 매수, 최대 MAX_POSITIONS종목
5. 종료 시 당일 요약을 Discord로 전송 (매수분은 다음날 아침에 매도)

모의투자 서버는 초당 호출 제한이 낮아 폴링 간격을 보수적으로 잡는다.
"""
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import db
import kis_order
import strategy
from alerts import _post as discord_post
from kis_auth import get_access_token
from main import load_watchlist

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
MARKET_OPEN = (9, 0)
ENTRY_CUTOFF = (15, 20)   # 이후엔 신규 진입 안 함 (종가 근접 매수 방지)
POLL_DELAY = 0.6          # 종목당 현재가 조회 간격 (모의서버 초당 2건 제한 대응)


def _now() -> datetime:
    return datetime.now(KST)


def _today() -> str:
    return _now().strftime("%Y%m%d")


def _wait_until(hour: int, minute: int) -> None:
    target = _now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    while _now() < target:
        time.sleep(min(30, max(1, (target - _now()).total_seconds())))


def refresh_daily_data() -> None:
    """전일봉까지 daily_candles를 최신화한다 (셋업 계산의 전제)."""
    from collect_history_fdr import collect_history_fdr

    summary = collect_history_fdr(years=1)
    if summary["failed"]:
        logger.warning("일봉 갱신 실패 종목 (전일 데이터가 없으면 해당 종목은 제외됨): %s", summary["failed"])


def sell_open_positions(access_token: str) -> list[str]:
    """오버나잇 포지션 전량 시장가 매도 (익일 시가 청산)."""
    sold = []
    for pos in db.get_open_positions("breakout"):  # ETF(지수 타이밍) 포지션은 제외
        try:
            kis_order.sell_market(access_token, pos["stock_code"], pos["qty"])
            quote = kis_order.get_current_price(access_token, pos["stock_code"])
            db.close_position(pos["id"], quote["price"], _today())
            sold.append(pos["stock_code"])
            logger.info("청산: %s x%d (매수가 %.0f -> 현재가 %d)",
                        pos["stock_code"], pos["qty"], pos["buy_price"], quote["price"])
        except Exception:
            logger.exception("%s 청산 실패 (다음 실행에서 재시도됨)", pos["stock_code"])
        time.sleep(POLL_DELAY)
    return sold


def calc_quantity(price: int) -> int:
    return max(0, config.TRADE_BUDGET_KRW // price)


def monitor_and_buy(access_token: str, setups: dict[str, dict]) -> list[str]:
    """돌파 감시 루프. 돌파 시 시장가 매수, 컷오프 시각까지 반복."""
    cutoff = _now().replace(hour=ENTRY_CUTOFF[0], minute=ENTRY_CUTOFF[1], second=0, microsecond=0)
    targets: dict[str, float] = {}   # 시가 확보 후 완성된 돌파가격
    bought: list[str] = []
    open_count = len(db.get_open_positions("breakout"))  # ETF 포지션은 슬롯을 차지하지 않음

    candidates = list(setups.keys())
    logger.info("감시 시작: 후보 %d종목, K=%.2f, 컷오프 %02d:%02d",
                len(candidates), config.TRADE_K, *ENTRY_CUTOFF)

    while _now() < cutoff and candidates and open_count < config.MAX_POSITIONS:
        for code in list(candidates):
            if _now() >= cutoff or open_count >= config.MAX_POSITIONS:
                break
            try:
                quote = kis_order.get_current_price(access_token, code)
            except Exception:
                logger.exception("%s 현재가 조회 실패, 다음 루프에서 재시도", code)
                time.sleep(POLL_DELAY)
                continue

            if code not in targets:
                if quote["open"] <= 0:
                    time.sleep(POLL_DELAY)
                    continue  # 아직 시가 미형성
                targets[code] = quote["open"] + config.TRADE_K * setups[code]["prev_range"]
                logger.info("%s: 시가 %d, 돌파가 %.0f", code, quote["open"], targets[code])

            if quote["price"] >= targets[code]:
                qty = calc_quantity(quote["price"])
                if qty <= 0:
                    logger.info("%s: 예산(%d원) 대비 가격이 높아 매수 불가", code, config.TRADE_BUDGET_KRW)
                    candidates.remove(code)
                else:
                    try:
                        kis_order.buy_market(access_token, code, qty)
                        db.add_position(code, qty, quote["price"], _today())
                        bought.append(code)
                        candidates.remove(code)
                        open_count += 1
                        logger.info("돌파 매수: %s x%d @ %d (돌파가 %.0f)", code, qty, quote["price"], targets[code])
                        discord_post(f":rocket: **[자동매매]** 돌파 매수 {code} x{qty} @ {quote['price']:,}원")
                    except Exception:
                        logger.exception("%s 매수 주문 실패", code)
            time.sleep(POLL_DELAY)

    return bought


def run_trading_day() -> dict:
    """하루치 매매 사이클 실행. 장 시작 전(08:5x)에 시작하는 것을 전제로 한다."""
    logger.info("=== 자동매매 시작 (%s, 모드: %s) ===", _today(), config.TRADING_MODE)
    db.init_db()

    refresh_daily_data()
    setups = strategy.compute_setups(load_watchlist())

    access_token = get_access_token()

    _wait_until(*MARKET_OPEN)
    time.sleep(60)  # 시가 형성/동시호가 직후 혼잡 회피

    sold = sell_open_positions(access_token)

    # 지수 타이밍 전략 (ETF_BUDGET_KRW > 0일 때만 동작, 돌파 전략과 자본 분리)
    try:
        import etf_timing

        etf_action = etf_timing.manage_position(access_token, _today())
    except Exception:
        logger.exception("ETF 타이밍 처리 실패 (돌파 전략은 계속 진행)")
        etf_action = "error"

    bought = monitor_and_buy(access_token, setups) if setups else []

    summary = {"date": _today(), "sold": sold, "bought": bought,
               "candidates": len(setups), "etf": etf_action}
    logger.info("=== 자동매매 종료: 청산 %s, 신규매수 %s, ETF %s ===",
                sold or "없음", bought or "없음", etf_action)
    discord_post(
        f":clipboard: **[자동매매 {_today()}]** 후보 {len(setups)}종목 / "
        f"청산 {len(sold)}건({', '.join(sold) if sold else '-'}) / "
        f"매수 {len(bought)}건({', '.join(bought) if bought else '-'}) / "
        f"ETF {etf_action}"
    )
    return summary
