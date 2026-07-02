"""일봉 과거 데이터 일괄 수집 (백테스트 준비용 원샷 스크립트).

watchlist의 모든 종목에 대해 과거 N년치 일봉을 받아 daily_candles 테이블에 저장한다.
매일 돌릴 필요는 없고, 백테스트 시작 전 한 번(또는 가끔 갱신용으로) 실행하면 된다.

사용법:
    python collect_history.py           # 기본 3년치
    python collect_history.py --years 5
"""
import argparse
import logging
import time

import db
from daily_collector import fetch_daily_history
from kis_auth import get_access_token
from logging_utils import configure_logging
from main import load_watchlist
from rate_limiter import chunk, get_batch_plan

logger = logging.getLogger(__name__)


def collect_history(years: int = 3, watchlist: list[str] | None = None) -> dict:
    watchlist = watchlist if watchlist is not None else load_watchlist()
    db.init_db()

    access_token = get_access_token()
    plan = get_batch_plan(len(watchlist))
    logger.info("일봉 %d년치 수집 시작: 종목 %d개", years, len(watchlist))

    summary = {"total_stocks": len(watchlist), "success": 0, "failed": [], "rows_saved": 0}

    batches = list(chunk(watchlist, plan.batch_size))
    for batch_idx, batch in enumerate(batches):
        for stock_code in batch:
            try:
                rows = fetch_daily_history(access_token, stock_code, years=years, call_delay=plan.call_delay)
                saved = db.upsert_daily_candles(rows)
                summary["success"] += 1
                summary["rows_saved"] += saved
                logger.info("%s: 일봉 %d개 저장 (%s ~ %s)",
                            stock_code, saved,
                            rows[0]["date"] if rows else "-",
                            rows[-1]["date"] if rows else "-")
            except Exception:
                logger.exception("%s 일봉 수집 실패", stock_code)
                summary["failed"].append(stock_code)
            time.sleep(plan.call_delay)

        if batch_idx < len(batches) - 1:
            time.sleep(plan.batch_delay)

    logger.info(
        "일봉 수집 완료: 성공 %d/%d, 저장 %d행, 실패 %s",
        summary["success"], summary["total_stocks"], summary["rows_saved"], summary["failed"],
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="일봉 과거 데이터 일괄 수집")
    parser.add_argument("--years", type=int, default=3, help="수집할 과거 기간(년), 기본 3년")
    args = parser.parse_args()

    configure_logging()
    collect_history(years=args.years)
