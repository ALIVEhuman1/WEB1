"""수집 결과를 Discord 웹훅으로 알림. DISCORD_WEBHOOK_URL이 설정된 경우에만
동작하며, 설정하지 않으면 조용히 아무 것도 하지 않는다 (opt-in).

- notify_collection_result: 매 수집 후 성공/실패 관계없이 현황 요약을 전송
- notify_completeness_result: 완결성 체크 후 결과 요약을 전송
"""
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


def notify_collection_result(summary: dict) -> None:
    """수집 완료 후 성공/실패 현황을 항상 전송한다."""
    if summary.get("failed"):
        _post(
            f":warning: **[분봉 수집기]** 성공 {summary['success']}/{summary['total_stocks']}종목, "
            f"{summary['rows_saved']}행 저장 / 실패: {', '.join(summary['failed'])}"
        )
    else:
        _post(
            f":white_check_mark: **[분봉 수집기]** 수집 완료 — "
            f"{summary['success']}/{summary['total_stocks']}종목, {summary['rows_saved']}행 저장"
        )


def notify_completeness_result(summary: dict) -> None:
    """완결성 체크 후 결과를 항상 전송한다."""
    if summary.get("still_incomplete"):
        _post(
            f":mag: **[완결성 체크]** {summary['date']} 재수집 후에도 데이터 부족 "
            f"{len(summary['still_incomplete'])}/{summary['checked']}종목: "
            f"{', '.join(summary['still_incomplete'])}"
        )
    elif summary.get("backfilled"):
        _post(
            f":white_check_mark: **[완결성 체크]** {summary['date']} 부족분 재수집 완료 — "
            f"보충된 종목: {', '.join(summary['backfilled'])}"
        )
    elif summary.get("incomplete"):
        # 전 종목 부족 -> 휴장일로 간주하고 재수집을 건너뛴 경우
        _post(f":calendar: **[완결성 체크]** {summary['date']} 휴장일로 판단되어 재수집을 건너뜀")
    else:
        _post(
            f":white_check_mark: **[완결성 체크]** {summary['date']} "
            f"{summary['checked']}종목 모두 데이터 정상"
        )
