"""매일 아침 종목별 진입 자격/돌파 폭 계산 (백테스트와 동일한 규칙).

- 돌파가격 = 당일 시가 + K * (전일 고가 - 전일 저가)
  -> 시가는 장 시작 후에야 알 수 있으므로 여기서는 prev_range까지만 계산하고,
     trader가 장중에 시가를 얻어 목표가를 완성한다.
- 거래량 필터: 전일 거래량 > 직전 20일 평균 거래량
- 시장 필터: 코스피 지수(KS11) 전일 종가 > 전일 기준 20일 이동평균
- 시장 폭 필터: 전종목 '자기 200일선 위' 비율 >= BREAKOUT_BREADTH_MIN (기본 40%)
  지수는 소수 대형주가 떠받쳐도 내부가 무너지는 국면을 걸러낸다. 2026-09 검증
  (전종목 2228개): 거래당 +0.212%->+0.626%, MDD -38.6%->-25.0%, 하락장 21-22는
  진입 0건으로 누적 -30.9%를 관망(0)으로 전환. 30/40/50% 세 임계 모두 개선되어
  견고성 확인. 전종목 일봉(collect_market.py)이 있어야 동작한다.

이 계산에 쓰는 daily_candles는 trader 시작 시(장 시작 전) 최신화되어 있어야 하며,
'마지막 행 = 전일'을 전제로 한다.
"""
import logging

import config
import db

logger = logging.getLogger(__name__)

VOL_WINDOW = 20
MA_LONG = 20
INDEX_CODE = "KS11"

BREADTH_MA = 200          # 종목별 '자기 200일선 위' 판단 기간
BREADTH_LOOKBACK = 260    # 최신 하루치만 필요하므로 최근 거래일로 계산 범위를 한정
BREADTH_MIN_STOCKS = 200  # 이보다 적으면 시장 폭을 신뢰할 수 없다고 본다


def market_breadth() -> tuple[float, int] | None:
    """전종목 '자기 200일선 위' 비율과 집계 종목수. 계산 불가 시 None.

    최신 저장 거래일(= 전일 종가) 기준이라 시장필터와 동일하게 미래참조가 없다.
    """
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT MIN(date) FROM (SELECT DISTINCT date FROM daily_candles "
            "WHERE stock_code != ? ORDER BY date DESC LIMIT ?)",
            (INDEX_CODE, BREADTH_LOOKBACK),
        ).fetchone()
        cutoff = row[0] if row else None
        if not cutoff:
            return None
        res = conn.execute(
            """
            SELECT AVG(CASE WHEN close > ma THEN 1.0 ELSE 0.0 END), COUNT(*)
            FROM (
                SELECT date, close,
                       AVG(close) OVER (PARTITION BY stock_code ORDER BY date
                                        ROWS BETWEEN ? PRECEDING AND CURRENT ROW) AS ma,
                       COUNT(*) OVER (PARTITION BY stock_code ORDER BY date
                                      ROWS BETWEEN ? PRECEDING AND CURRENT ROW) AS cnt
                FROM daily_candles
                WHERE stock_code != ? AND date >= ?
            )
            WHERE cnt = ? AND date = (SELECT MAX(date) FROM daily_candles WHERE stock_code != ?)
            """,
            (BREADTH_MA - 1, BREADTH_MA - 1, INDEX_CODE, cutoff, BREADTH_MA, INDEX_CODE),
        ).fetchone()
    if not res or res[1] is None or res[1] == 0:
        return None
    return float(res[0]), int(res[1])


def breadth_ok() -> bool:
    """시장 폭이 임계 이상이면 진입 허용 (백테스트 breakout_bd와 동일 규칙).

    지수는 소수 대형주가 떠받쳐도 내부가 무너지는 국면을 걸러낸다.
    config.BREAKOUT_BREADTH_MIN <= 0이면 비활성(항상 허용).
    계산 불가(전종목 일봉 부족) 시에는 '보호 없이 매매'하지 않도록 진입을 막는다.
    """
    threshold = config.BREAKOUT_BREADTH_MIN
    if threshold <= 0:
        return True

    result = market_breadth()
    if result is None or result[1] < BREADTH_MIN_STOCKS:
        n = 0 if result is None else result[1]
        logger.warning(
            "시장 폭 계산 불가(집계 %d종목 < %d). 전종목 일봉이 필요합니다 "
            "(collect_market.py --init). 보호 없이 매매하지 않도록 오늘 신규 진입을 막습니다. "
            "필터를 끄려면 .env에 BREAKOUT_BREADTH_MIN=0",
            n, BREADTH_MIN_STOCKS,
        )
        return False

    ratio, n = result
    ok = ratio >= threshold
    logger.info("시장 폭 필터: 200일선 위 %.1f%% (%d종목) vs 임계 %.0f%% -> %s",
                ratio * 100, n, threshold * 100, "진입 허용" if ok else "진입 금지(내부 약화)")
    return ok


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
    if not breadth_ok():
        logger.info("시장 폭 필터 미통과 -> 오늘은 신규 진입 없음")
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
