"""일봉 과거 데이터 일괄 수집 (백테스트 준비용 원샷 스크립트).

watchlist의 모든 종목에 대해 과거 N년치 일봉을 받아 daily_candles 테이블에 저장한다.
매일 돌릴 필요는 없고, 백테스트 시작 전 한 번(또는 가끔 갱신용으로) 실행하면 된다.

실패한 종목은 일정 시간 대기 후 자동으로 재시도한다 (KIS 서버가 심야 점검 등으로
장시간 500을 뱉는 경우에 대응). 성공한 종목은 재시도하지 않는다.

사용법:
    python collect_history.py                          # 기본 3년치
    python collect_history.py --years 5
    python collect_history.py --years 5 --retry-rounds 10 --retry-wait 1800
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


def collect_history_with_retry(years: int = 3, watchlist: list[str] | None = None,
                               retry_rounds: int = 6, retry_wait: int = 600) -> dict:
    """수집 후 실패 종목이 있으면 retry_wait초 대기 후 실패분만 재시도한다.

    KIS 서버 점검(수십 분~수 시간)에도 버틸 수 있도록, 기본값은 10분 간격 6회
    (약 1시간)이며 nohup으로 띄워두면 알아서 끝까지 채우고 종료한다.
    """
    watchlist = watchlist if watchlist is not None else load_watchlist()

    total = {"total_stocks": len(watchlist), "success": 0, "failed": [], "rows_saved": 0}
    remaining = watchlist

    for round_idx in range(retry_rounds + 1):
        if round_idx > 0:
            logger.info(
                "[재시도 %d/%d] 실패 %d종목, %d초 대기 후 재시도: %s",
                round_idx, retry_rounds, len(remaining), retry_wait, remaining,
            )
            time.sleep(retry_wait)

        summary = collect_history(years=years, watchlist=remaining)
        total["success"] += summary["success"]
        total["rows_saved"] += summary["rows_saved"]
        remaining = summary["failed"]

        if not remaining:
            break

    total["failed"] = remaining
    if remaining:
        logger.error("최종 실패 (%d회 재시도 후에도 실패): %s", retry_rounds, remaining)
    else:
        logger.info("최종 완료: 전 종목 성공 (%d/%d, 총 %d행)",
                    total["success"], total["total_stocks"], total["rows_saved"])
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="일봉 과거 데이터 일괄 수집")
    parser.add_argument("--years", type=int, default=3, help="수집할 과거 기간(년), 기본 3년")
    parser.add_argument("--retry-rounds", type=int, default=6, help="실패 종목 재시도 횟수 (기본 6회)")
    parser.add_argument("--retry-wait", type=int, default=600, help="재시도 간 대기 시간(초, 기본 600=10분)")
    args = parser.parse_args()

    configure_logging()
    collect_history_with_retry(years=args.years, retry_rounds=args.retry_rounds, retry_wait=args.retry_wait)
