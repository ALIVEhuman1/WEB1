"""매일 아침 종목별 진입 자격/돌파 폭 계산 (백테스트와 동일한 규칙).

- 돌파가격 = 당일 시가 + K * (전일 고가 - 전일 저가)
  -> 시가는 장 시작 후에야 알 수 있으므로 여기서는 prev_range까지만 계산하고,
     trader가 장중에 시가를 얻어 목표가를 완성한다.
- 거래량 필터: 전일 거래량 > 직전 20일 평균 거래량
- 시장 필터: 코스피 지수(KS11) 전일 종가 > 전일 기준 20일 이동평균

이 계산에 쓰는 daily_candles는 trader 시작 시(장 시작 전) 최신화되어 있어야 하며,
'마지막 행 = 전일'을 전제로 한다.
"""
import logging

import db

logger = logging.getLogger(__name__)

VOL_WINDOW = 20
MA_LONG = 20
INDEX_CODE = "KS11"


def market_regime_ok() -> bool:
    """전일 기준 코스피 종가 > 20일 이동평균인지."""
    rows = db.get_daily_candles(INDEX_CODE)
    if len(rows) < MA_LONG:
        raise RuntimeError(f"지수({INDEX_CODE}) 데이터 부족: collect_history_fdr.py를 먼저 실행하세요.")
    closes = [r["close"] for r in rows[-MA_LONG:]]
    ma = sum(closes) / len(closes)
    latest_close = rows[-1]["close"]
    ok = latest_close > ma
    logger.info("시장 필터: 코스피 %s vs MA%d %.1f -> %s", latest_close, MA_LONG, ma, "진입 허용" if ok else "진입 금지")
    return ok


def get_stock_setup(stock_code: str) -> dict | None:
    """종목의 전일 변동폭과 거래량 필터 통과 여부. 데이터 부족 시 None."""
    rows = db.get_daily_candles(stock_code)
    if len(rows) < VOL_WINDOW + 1:
        return None

    prev = rows[-1]
    prev_range = prev["high"] - prev["low"]
    if prev_range <= 0:
        return None

    # 전일 거래량 vs 그 이전 20일 평균 (전일 제외)
    vol_window = [r["volume"] for r in rows[-(VOL_WINDOW + 1):-1]]
    vol_avg = sum(vol_window) / len(vol_window)
    vol_ok = prev["volume"] > vol_avg

    return {
        "stock_code": stock_code,
        "prev_date": prev["date"],
        "prev_range": prev_range,
        "vol_ok": vol_ok,
    }


def compute_setups(watchlist: list[str]) -> dict[str, dict]:
    """진입 자격을 통과한 종목만 {종목코드: 셋업} 형태로 반환한다."""
    if not market_regime_ok():
        logger.info("시장 필터 미통과 -> 오늘은 신규 진입 없음")
        return {}

    setups = {}
    for code in watchlist:
        setup = get_stock_setup(code)
        if setup is None:
            logger.warning("%s: 일봉 데이터 부족으로 제외", code)
            continue
        if not setup["vol_ok"]:
            continue
        setups[code] = setup

    logger.info("진입 후보: %d/%d 종목 (거래량 필터 통과)", len(setups), len(watchlist))
    return setups
