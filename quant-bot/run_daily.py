"""cron/스케줄러 실행 트리거. 수집 로직은 main.collect_and_store()에 있고,
이 파일은 로그 파일 설정 후 그 함수를 호출하기만 한다.

crontab 예시 (매일 장마감 후 15:40 실행):
    40 15 * * 1-5 cd /path/to/quant-bot && /path/to/venv/bin/python run_daily.py
"""
import logging

import config

config.LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_DIR / "collector.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from main import collect_and_store  # noqa: E402  (로깅 설정 이후 임포트)

if __name__ == "__main__":
    collect_and_store()
