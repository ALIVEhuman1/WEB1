"""국내주식기간별시세(FHKST03010100)로 일봉 과거 데이터 수집.

한 번 호출에 최대 100봉까지만 반환되므로, 조회 구간을 과거로 옮겨가며
반복 호출해 수년치 일봉을 수집한다. 수정주가 기준으로 받아 백테스트 시
액면분할/증자 왜곡을 줄인다.
"""
import logging
import time
from datetime import datetime, timedelta

import requests

import config
from retry import retry_with_backoff

logger = logging.getLogger(__name__)

ENDPOINT_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
TR_ID = "FHKST03010100"
MAX_BARS_PER_CALL = 100  # API가 한 번에 주는 최대 일봉 수
MAX_PAGES = 40           # 안전 상한 (100봉 * 40 = 약 16년치)


def _headers(access_token: str) -> dict:
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": TR_ID,
    }


@retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(requests.RequestException,))
def _request_daily_chart(access_token: str, stock_code: str, start_date: str, end_date: str) -> dict:
    url = config.get_base_url() + ENDPOINT_PATH
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D",   # 일봉
        "FID_ORG_ADJ_PRC": "0",       # 0=수정주가, 1=원주가
    }
    resp = requests.get(url, headers=_headers(access_token), params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(f"KIS API 오류 ({stock_code}): {payload.get('msg1')}")
    return payload


def _parse_daily_rows(stock_code: str, payload: dict) -> list[dict]:
    rows = []
    for item in payload.get("output2", []):
        if not item.get("stck_bsop_date"):
            continue  # 빈 항목 방어
        rows.append({
            "stock_code": stock_code,
            "date": item["stck_bsop_date"],
            "open": int(item["stck_oprc"]),
            "high": int(item["stck_hgpr"]),
            "low": int(item["stck_lwpr"]),
            "close": int(item["stck_clpr"]),
            "volume": int(item["acml_vol"]),
        })
    return rows


def fetch_daily_history(
    access_token: str,
    stock_code: str,
    years: int = 3,
    call_delay: float = 0.2,
) -> list[dict]:
    """오늘부터 과거 years년치 일봉을 페이지네이션으로 수집한다."""
    end = datetime.now()
    oldest_target = end - timedelta(days=years * 365)

    collected: dict[str, dict] = {}
    cursor_end = end

    for page in range(MAX_PAGES):
        # 100봉이 대략 5개월치이므로 구간을 넉넉히 200일로 잡는다
        cursor_start = cursor_end - timedelta(days=200)
        payload = _request_daily_chart(
            access_token,
            stock_code,
            cursor_start.strftime("%Y%m%d"),
            cursor_end.strftime("%Y%m%d"),
        )
        rows = _parse_daily_rows(stock_code, payload)
        if not rows:
            break  # 상장 이전 구간까지 도달

        for row in rows:
            collected[row["date"]] = row

        oldest_got = min(row["date"] for row in rows)
        if oldest_got <= oldest_target.strftime("%Y%m%d"):
            break

        cursor_end = datetime.strptime(oldest_got, "%Y%m%d") - timedelta(days=1)
        if page < MAX_PAGES - 1:
            time.sleep(call_delay)

    result = sorted(collected.values(), key=lambda r: r["date"])
    # 목표 기간보다 오래된 데이터는 잘라낸다
    cutoff = oldest_target.strftime("%Y%m%d")
    return [r for r in result if r["date"] >= cutoff]
