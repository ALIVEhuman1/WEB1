"""로그 타임스탬프를 KST(Asia/Seoul) 기준으로 고정한다.
클라우드 실행 환경은 보통 컨테이너 자체 TZ가 UTC라, 로그만 보고 국내 장 시간과
맞춰보려면 별도 변환이 필요해 로거 포맷터 단에서 강제로 KST를 사용한다."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


class KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=KST)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S KST")


def configure_logging(log_file: str | None = None) -> None:
    formatter = KSTFormatter("%(asctime)s [%(levelname)s] %(message)s")

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = handlers
