"""KIS 주문/시세 API 래퍼 (현재가 조회, 시장가 매수/매도, 잔고 조회).

모의투자(vps)와 실전투자(prod)의 tr_id가 다르므로 TRADING_MODE에 따라 자동 선택한다.
안전을 위해 실전 모드에서는 ALLOW_PROD_TRADING=true 환경변수가 없으면 주문을 거부한다.
"""
import logging
import os

import requests

import config
from retry import retry_with_backoff

logger = logging.getLogger(__name__)

PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
HASHKEY_PATH = "/uapi/hashkey"

TR_PRICE = "FHKST01010100"


def _tr_buy() -> str:
    return "VTTC0802U" if config.TRADING_MODE == "vps" else "TTTC0802U"


def _tr_sell() -> str:
    return "VTTC0801U" if config.TRADING_MODE == "vps" else "TTTC0801U"


def _assert_trading_allowed() -> None:
    if config.TRADING_MODE == "prod" and os.getenv("ALLOW_PROD_TRADING", "").lower() != "true":
        raise RuntimeError(
            "실전투자(prod) 모드에서 주문이 차단되었습니다. "
            "정말 실계좌로 주문하려면 .env에 ALLOW_PROD_TRADING=true를 명시하세요."
        )


def _headers(access_token: str, tr_id: str, hashkey: str | None = None) -> dict:
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": tr_id,
    }
    if hashkey:
        headers["hashkey"] = hashkey
    return headers


def _get_hashkey(body: dict) -> str:
    url = config.get_base_url() + HASHKEY_PATH
    headers = {
        "content-type": "application/json; charset=utf-8",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()["HASH"]


@retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(requests.RequestException,))
def get_current_price(access_token: str, stock_code: str) -> dict:
    """현재가/당일시가 조회. 반환: {"price": 현재가, "open": 당일시가}"""
    url = config.get_base_url() + PRICE_PATH
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
    resp = requests.get(url, headers=_headers(access_token, TR_PRICE), params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(f"현재가 조회 오류 ({stock_code}): {payload.get('msg1')}")
    out = payload["output"]
    return {"price": int(out["stck_prpr"]), "open": int(out["stck_oprc"])}


@retry_with_backoff(max_retries=2, base_delay=1.0, exceptions=(requests.RequestException,))
def _order_market(access_token: str, stock_code: str, qty: int, tr_id: str) -> dict:
    _assert_trading_allowed()
    cano, prdt = config._split_account()
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "PDNO": stock_code,
        "ORD_DVSN": "01",       # 시장가
        "ORD_QTY": str(qty),
        "ORD_UNPR": "0",
    }
    url = config.get_base_url() + ORDER_PATH
    hashkey = _get_hashkey(body)
    resp = requests.post(url, headers=_headers(access_token, tr_id, hashkey), json=body, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(f"주문 실패 ({stock_code} x{qty}, {tr_id}): {payload.get('msg1')}")
    return payload.get("output", {})


def buy_market(access_token: str, stock_code: str, qty: int) -> dict:
    """시장가 매수."""
    logger.info("시장가 매수 주문: %s x%d", stock_code, qty)
    return _order_market(access_token, stock_code, qty, _tr_buy())


def sell_market(access_token: str, stock_code: str, qty: int) -> dict:
    """시장가 매도."""
    logger.info("시장가 매도 주문: %s x%d", stock_code, qty)
    return _order_market(access_token, stock_code, qty, _tr_sell())
