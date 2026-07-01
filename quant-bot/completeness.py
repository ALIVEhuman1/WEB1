"""당일 수집된 분봉이 충분한지 검증하고, 부족한 종목만 다시 수집한다.

장마감 직후 수집(main.collect_and_store)에서 API 순간 장애 등으로 일부 분봉이
비어 있을 수 있어, 야간에 한 번 더 돌려 개수를 점검하고 부족하면 재수집한다.
"""
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import db
import main
from collector import fetch_full_day_candles
from kis_auth import get_access_token
from rate_limiter import chunk, get_batch_plan

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
EXPECTED_BARS = 390  # 정규장 09:00~15:30 (6.5시간 * 60분)
MIN_COMPLETE_RATIO = 0.9


def _today_kst() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def _count_bars(stock_code: str, date: str) -> int:
    return len(db.get_candles(stock_code, start_date=date, end_date=date))


def check_and_backfill(watchlist: list[str] | None = None, target_date: str | None = None) -> dict:
    """지정한 날짜(기본 오늘, KST)의 분봉 개수를 확인하고, 기준치 미달 종목만 재수집한다."""
    watchlist = watchlist if watchlist is not None else main.load_watchlist()
    target_date = target_date or _today_kst()
    db.init_db()

    threshold = EXPECTED_BARS * MIN_COMPLETE_RATIO
    incomplete = [code for code in watchlist if _count_bars(code, target_date) < threshold]

    summary = {
        "date": target_date,
        "checked": len(watchlist),
        "incomplete": incomplete,
        "backfilled": [],
        "still_incomplete": [],
    }

    if not incomplete:
        logger.info("완결성 체크 완료 (%s): %d종목 모두 정상", target_date, len(watchlist))
        return summary

    if len(incomplete) == len(watchlist):
        # 전 종목이 다 부족하면 실제 수집 문제보다 휴장일일 가능성이 높다.
        # (KRX 공휴일 캘린더는 아직 연동하지 않았으므로 이 휴리스틱으로 오탐을 줄인다.)
        logger.info(
            "완결성 체크 (%s): 전 종목 데이터 부족 -> 휴장일 가능성이 높아 재수집을 건너뜁니다",
            target_date,
        )
        return summary

    logger.info("완결성 체크 (%s): %d종목 부족 발견 -> 재수집 시도: %s", target_date, len(incomplete), incomplete)

    access_token = get_access_token()
    plan = get_batch_plan(len(incomplete))

    batches = list(chunk(incomplete, plan.batch_size))
    for batch_idx, batch in enumerate(batches):
        for stock_code in batch:
            try:
                rows = fetch_full_day_candles(access_token, stock_code, call_delay=plan.call_delay)
                db.upsert_candles(rows)
                if _count_bars(stock_code, target_date) >= threshold:
                    summary["backfilled"].append(stock_code)
                    logger.info("%s: 재수집으로 완결성 충족", stock_code)
                else:
                    summary["still_incomplete"].append(stock_code)
                    logger.warning("%s: 재수집 후에도 데이터 부족", stock_code)
            except Exception:
                logger.exception("%s 재수집 실패", stock_code)
                summary["still_incomplete"].append(stock_code)
            time.sleep(plan.call_delay)

        if batch_idx < len(batches) - 1:
            time.sleep(plan.batch_delay)

    return summary


if __name__ == "__main__":
    from logging_utils import configure_logging

    configure_logging()
    check_and_backfill()
