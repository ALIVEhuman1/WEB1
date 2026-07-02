"""야간에 당일 분봉 완결성을 검증하고 부족하면 재수집하는 실행 트리거.

crontab 예시 (매일 22:00 KST, 장마감 수집이 끝나고 데이터가 안정된 시점):
    0 22 * * 1-5 cd /path/to/quant-bot && /path/to/venv/bin/python run_completeness_check.py
"""
import logging

import config
from logging_utils import configure_logging

config.LOG_DIR.mkdir(parents=True, exist_ok=True)
configure_logging(str(config.LOG_DIR / "completeness.log"))

import alerts  # noqa: E402  (로깅 설정 이후 임포트)
from completeness import check_and_backfill  # noqa: E402
from lock import single_instance_lock  # noqa: E402

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        with single_instance_lock():
            summary = check_and_backfill()
            alerts.notify_completeness_result(summary)
    except RuntimeError as exc:
        logger.warning(str(exc))
