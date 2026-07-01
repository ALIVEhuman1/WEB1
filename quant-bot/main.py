"""수집 로직 본체: watchlist 순회 -> 분봉 수집 -> DB 저장.

이 모듈은 로직만 담당하며, 실행 트리거(수동 실행/cron)는 run_daily.py 등
별도 파일에서 이 모듈의 collect_and_store()를 호출하는 방식으로 분리한다.
"""
import json
import logging
import time

import config
import db
import gcs_sync
from collector import fetch_full_day_candles
from kis_auth import get_access_token
from rate_limiter import chunk, get_batch_plan

logger = logging.getLogger(__name__)


def load_watchlist() -> list[str]:
    with open(config.WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_and_store(watchlist: list[str] | None = None) -> dict:
    """watchlist의 모든 종목에 대해 당일 분봉을 수집하고 DB에 저장한다.

    GCS_BUCKET_NAME이 설정되어 있으면(Cloud Run Job처럼 실행마다 컨테이너가
    초기화되는 환경) 실행 전 GCS에서 기존 DB를 내려받고, 종료 후 다시 올린다.
    """
    watchlist = watchlist if watchlist is not None else load_watchlist()
    gcs_sync.download_db()
    db.init_db()

    access_token = get_access_token()
    plan = get_batch_plan(len(watchlist))
    logger.info(
        "수집 시작: 종목 %d개, batch_size=%d, call_delay=%.2fs, batch_delay=%.2fs",
        len(watchlist), plan.batch_size, plan.call_delay, plan.batch_delay,
    )

    summary = {"total_stocks": len(watchlist), "success": 0, "failed": [], "rows_saved": 0}

    batches = list(chunk(watchlist, plan.batch_size))
    for batch_idx, batch in enumerate(batches):
        for stock_code in batch:
            try:
                rows = fetch_full_day_candles(access_token, stock_code, call_delay=plan.call_delay)
                saved = db.upsert_candles(rows)
                summary["success"] += 1
                summary["rows_saved"] += saved
                logger.info("%s: %d개 분봉 저장", stock_code, saved)
            except Exception:
                logger.exception("%s 수집 실패", stock_code)
                summary["failed"].append(stock_code)
            time.sleep(plan.call_delay)

        if batch_idx < len(batches) - 1:
            time.sleep(plan.batch_delay)

    logger.info(
        "수집 완료: 성공 %d/%d, 저장 %d행, 실패 %s",
        summary["success"], summary["total_stocks"], summary["rows_saved"], summary["failed"],
    )
    gcs_sync.upload_db()
    return summary


if __name__ == "__main__":
    from logging_utils import configure_logging

    configure_logging()
    collect_and_store()
