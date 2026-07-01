"""수집 실패/완결성 부족 시 Discord 웹훅 알림. DISCORD_WEBHOOK_URL이 설정된 경우에만
동작하며, 설정하지 않으면 조용히 아무 것도 하지 않는다 (opt-in)."""
import logging
import os

import requests

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def _post(text: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=5)
    except requests.RequestException:
        logger.exception("Discord 알림 전송 실패")


def notify_failure(summary: dict) -> None:
    if not summary.get("failed"):
        return
    _post(
        f":warning: **[분봉 수집기]** 실패 {len(summary['failed'])}/{summary['total_stocks']}종목: "
        f"{', '.join(summary['failed'])}"
    )


def notify_incomplete(summary: dict) -> None:
    if not summary.get("still_incomplete"):
        return
    _post(
        f":mag: **[완결성 체크]** {summary['date']} 재수집 후에도 데이터 부족한 종목 "
        f"{len(summary['still_incomplete'])}/{summary['checked']}: {', '.join(summary['still_incomplete'])}"
    )
