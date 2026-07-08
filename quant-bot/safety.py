"""시장 급락/누적손실 대응 안전장치 (kill-switch).

통계적 수익 엣지를 노리는 '매매법'이 아니라, 백테스트로 검증 불가능한 꼬리위험
(플래시 크래시·서킷브레이커 같은 당일 급락, 연속 손실)으로부터 계좌를 지키는
리스크 관리 로직이다. 표본이 없어 최적화할 수 없으니 백테스트 없이 그냥 켠다.

- 급락 서킷: 코스피(KODEX200 대용) 당일 등락률이 CRASH_HALT_PCT 이하이면 그날 신규 진입 중단.
  (우리 신호는 전부 전일 종가 기반이라 '당일' 급락엔 반응이 늦은 빈틈을 메운다.)
- 손실 차단기: 실현 누적손익이 -LOSS_LIMIT_KRW 이하이면 신규 진입 중단 + 사람에게 알림.
"""
import logging

import config
import db
import kis_order

logger = logging.getLogger(__name__)

MARKET_PROXY = "069500"  # KODEX 200 (코스피 지수 대용, 기존 시세 API로 조회 가능)


def market_change_pct(access_token: str) -> float | None:
    """코스피 당일 등락률(%) 근사치. 조회 실패 시 None (안전측: 매매 계속)."""
    try:
        quote = kis_order.get_current_price(access_token, MARKET_PROXY)
    except Exception:
        logger.exception("급락 체크용 시세 조회 실패 (급락 서킷 이번 회차 미적용)")
        return None
    return quote.get("change_pct")


def crash_halt(access_token: str) -> tuple[bool, float | None]:
    """당일 등락률이 임계치 이하이면 (True, pct), 아니면 (False, pct). 조회 실패 시 (False, None)."""
    pct = market_change_pct(access_token)
    if pct is None:
        return False, None
    return pct <= config.CRASH_HALT_PCT, pct


def realized_pnl() -> int:
    """청산 완료된 포지션들의 실현 누적손익(원). 미실현분은 포함하지 않는다."""
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM((sell_price - buy_price) * qty), 0) "
            "FROM positions WHERE status = 'closed' AND sell_price IS NOT NULL"
        ).fetchone()
    return int(row[0])


def loss_limit_halt() -> tuple[bool, int]:
    """실현 누적손익이 -LOSS_LIMIT_KRW 이하이면 (True, pnl). LOSS_LIMIT_KRW<=0이면 비활성."""
    pnl = realized_pnl()
    if config.LOSS_LIMIT_KRW <= 0:
        return False, pnl
    return pnl <= -config.LOSS_LIMIT_KRW, pnl
