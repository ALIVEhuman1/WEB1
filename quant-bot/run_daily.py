"""cron/스케줄러 실행 트리거. 수집 로직은 main.collect_and_store()에 있고,
이 파일은 로깅/중복실행 방지/실패 알림만 감싸서 그 함수를 호출한다.

crontab 예시 (매일 장마감 후 15:40 실행, KST):
    40 15 * * 1-5 cd /path/to/quant-bot && /path/to/venv/bin/python run_daily.py

Cloud Run Job으로 배포하는 경우 컨테이너 ENTRYPOINT로 이 파일을 실행하면 된다.
"""
import logging

import config
from logging_utils import configure_logging

config.LOG_DIR.mkdir(parents=True, exist_ok=True)
configure_logging(str(config.LOG_DIR / "collector.log"))

import alerts  # noqa: E402  (로깅 설정 이후 임포트)
from lock import single_instance_lock  # noqa: E402
from main import collect_and_store  # noqa: E402

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        with single_instance_lock():
            summary = collect_and_store()
            alerts.notify_collection_result(summary)
    except RuntimeError as exc:
        logger.warning(str(exc))
