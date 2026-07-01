"""주식당일분봉조회(FHKST03010200) 호출 및 응답 파싱."""
import time

import requests

import config
from retry import retry_with_backoff

ENDPOINT_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
TR_ID = "FHKST03010200"
MARKET_OPEN_TIME = "090000"
MAX_PAGES = 20  # 페이지네이션 안전 상한 (하루 390분 / 30분씩 조회해도 20페이지면 충분)


def _headers(access_token: str) -> dict:
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": TR_ID,
    }


@retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(requests.RequestException,))
def _request_chart(access_token: str, stock_code: str, input_hour: str, include_past: str = "Y") -> dict:
    url = config.get_base_url() + ENDPOINT_PATH
    params = {
        "FID_ETC_CLS_CODE": "",
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_HOUR_1": input_hour,
        "FID_PW_DATA_INCU_YN": include_past,
    }
    resp = requests.get(url, headers=_headers(access_token), params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(f"KIS API 오류 ({stock_code}): {payload.get('msg1')}")
    return payload


def _parse_rows(stock_code: str, payload: dict) -> list[dict]:
    rows = []
    for item in payload.get("output2", []):
        rows.append({
            "stock_code": stock_code,
            "date": item["stck_bsop_date"],
            "time": item["stck_cntg_hour"],
            "open": int(item["stck_oprc"]),
            "high": int(item["stck_hgpr"]),
            "low": int(item["stck_lwpr"]),
            "close": int(item["stck_prpr"]),
            "volume": int(item["cntg_vol"]),
        })
    return rows


def fetch_minute_chart(access_token: str, stock_code: str, input_hour: str = "153000") -> list[dict]:
    """단일 호출로 input_hour 이전 분봉(최대 약 30개)을 가져온다."""
    payload = _request_chart(access_token, stock_code, input_hour)
    return _parse_rows(stock_code, payload)


def fetch_full_day_candles(
    access_token: str,
    stock_code: str,
    end_hour: str = "153000",
    call_delay: float = 0.15,
) -> list[dict]:
    """개장(09:00)부터 end_hour까지 당일 분봉 전체를 페이지네이션으로 수집한다."""
    collected: dict[tuple[str, str], dict] = {}
    cursor_hour = end_hour

    for page in range(MAX_PAGES):
        rows = fetch_minute_chart(access_token, stock_code, cursor_hour)
        if not rows:
            break

        for row in rows:
            collected[(row["date"], row["time"])] = row

        oldest_time = min(row["time"] for row in rows)
        if oldest_time <= MARKET_OPEN_TIME:
            break

        cursor_hour = oldest_time
        if page < MAX_PAGES - 1:
            time.sleep(call_delay)

    return sorted(collected.values(), key=lambda r: (r["date"], r["time"]))
