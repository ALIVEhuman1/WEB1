"""수집 실패 시 Discord 웹훅 알림. DISCORD_WEBHOOK_URL이 설정된 경우에만 동작하며,
설정하지 않으면 조용히 아무 것도 하지 않는다 (opt-in)."""
import logging
import os

import requests

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def notify_failure(summary: dict) -> None:
    if not DISCORD_WEBHOOK_URL or not summary.get("failed"):
        return

    text = (
        f":warning: **[분봉 수집기]** 실패 {len(summary['failed'])}/{summary['total_stocks']}종목: "
        f"{', '.join(summary['failed'])}"
    )
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=5)
    except requests.RequestException:
        logger.exception("Discord 알림 전송 실패")
