"""KIS Open API OAuth 접근토큰 발급 및 파일 캐싱.

KIS는 토큰 재발급에 분당 호출 제한이 있어, 만료 임박(REFRESH_BUFFER 이내) 전에는
캐시된 토큰을 그대로 재사용한다.
"""
import json
from datetime import datetime, timedelta

import requests

import config
from retry import retry_with_backoff

TOKEN_URL_PATH = "/oauth2/tokenP"
REFRESH_BUFFER = timedelta(minutes=10)


def _read_cache() -> dict | None:
    if not config.TOKEN_CACHE_PATH.exists():
        return None
    try:
        with open(config.TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("mode") != config.TRADING_MODE:
        return None
    return data


def _write_cache(access_token: str, expires_at: datetime) -> None:
    data = {
        "access_token": access_token,
        "expires_at": expires_at.isoformat(),
        "mode": config.TRADING_MODE,
    }
    with open(config.TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


@retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(requests.RequestException,))
def _request_new_token() -> tuple[str, datetime]:
    if not config.APP_KEY or not config.APP_SECRET:
        raise RuntimeError("KIS_APP_KEY / KIS_APP_SECRET이 .env에 설정되어 있지 않습니다.")

    url = config.get_base_url() + TOKEN_URL_PATH
    body = {
        "grant_type": "client_credentials",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
    }
    resp = requests.post(url, json=body, timeout=10)
    resp.raise_for_status()
    payload = resp.json()

    access_token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 86400))
    expires_at = datetime.now() + timedelta(seconds=expires_in)
    return access_token, expires_at


def get_access_token(force_refresh: bool = False) -> str:
    """유효한 접근토큰을 반환한다. 캐시가 유효하면 재발급 없이 그대로 사용한다."""
    if not force_refresh:
        cached = _read_cache()
        if cached:
            expires_at = datetime.fromisoformat(cached["expires_at"])
            if datetime.now() + REFRESH_BUFFER < expires_at:
                return cached["access_token"]

    access_token, expires_at = _request_new_token()
    _write_cache(access_token, expires_at)
    return access_token
