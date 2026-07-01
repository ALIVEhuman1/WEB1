"""수집 실패 시 Slack 웹훅 알림. SLACK_WEBHOOK_URL이 설정된 경우에만 동작하며,
설정하지 않으면 조용히 아무 것도 하지 않는다 (opt-in)."""
import logging
import os

import requests

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def notify_failure(summary: dict) -> None:
    if not SLACK_WEBHOOK_URL or not summary.get("failed"):
        return

    text = (
        f":warning: [분봉 수집기] 실패 {len(summary['failed'])}/{summary['total_stocks']}종목: "
        f"{', '.join(summary['failed'])}"
    )
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=5)
    except requests.RequestException:
        logger.exception("Slack 알림 전송 실패")
