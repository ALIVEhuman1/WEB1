"""자동매매 실행 트리거 (cron 진입점).

crontab 예시 (평일 08:55 KST 시작, 장 시작 전 셋업 계산 후 하루 종일 매매):
    55 8 * * 1-5 cd /path/to/quant-bot && /path/to/venv/bin/python run_trader.py
"""
import logging

import config
from logging_utils import configure_logging

config.LOG_DIR.mkdir(parents=True, exist_ok=True)
configure_logging(str(config.LOG_DIR / "trader.log"))

from lock import single_instance_lock  # noqa: E402  (로깅 설정 이후 임포트)
from trader import run_trading_day  # noqa: E402

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        with single_instance_lock("trader"):
            run_trading_day()
    except RuntimeError as exc:
        logger.warning(str(exc))
    except Exception:
        logger.exception("자동매매 비정상 종료")
        from alerts import _post
        _post(":rotating_light: **[자동매매]** 비정상 종료 - logs/trader.log 확인 필요")
