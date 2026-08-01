"""KIS 해외주식(미국) 주문/시세 래퍼 — 현재가 조회, 지정가 매수/매도.

국내(kis_order.py)와 분리된 이유:
- 해외주식은 엔드포인트·TR ID·거래소코드·주문파라미터가 전혀 다르다.
- 미국은 시장가 주문이 없어 '지정가'만 쓴다. 즉시체결을 위해 현재가 대비
  버퍼(config.US_ORDER_SLIPPAGE)를 얹은 지정가로 낸다 (매수 +, 매도 -).

⚠️ 중요: 이 모듈의 TR ID와 거래소코드 상수는 KIS 문서 기준으로 작성했으나
   계정/버전에 따라 다를 수 있다. 실주문 전 반드시 KIS Developers 최신 문서와
   대조하고, 모의투자(vps)로 1주 테스트해 응답을 확인할 것.
   (모의투자·예산 0 기본이라 검증 전엔 실돈이 나가지 않는다.)

안전장치는 국내와 동일: 실전(prod)에서는 ALLOW_PROD_TRADING=true가 없으면 주문 거부.
"""
import logging
import os

import requests

import config
from retry import retry_with_backoff

logger = logging.getLogger(__name__)

PRICE_PATH = "/uapi/overseas-price/v1/quotations/price"
ORDER_PATH = "/uapi/overseas-stock/v1/trading/order"
HASHKEY_PATH = "/uapi/hashkey"

TR_PRICE = "HHDFS00000300"   # 해외주식 현재가

# 미국 주간거래 주문 TR (모의=V, 실전=T). ⚠️ KIS 문서와 대조 필요.
_TR_BUY = {"vps": "VTTT1002U", "prod": "TTTT1002U"}
_TR_SELL = {"vps": "VTTT1001U", "prod": "TTTT1006U"}

# 거래소코드: 주문(4자리)과 시세조회(3자리)가 다르다. ⚠️ KIS 문서와 대조 필요.
ORDER_EXCD = {"NASD", "NYSE", "AMEX"}
_PRICE_EXCD = {"NASD": "NAS", "NYSE": "NYS", "AMEX": "AMS"}

# 심볼별 주문 거래소 코드. 미지정 시 기본 NASD. ETF(SPY/QQQ)는 NYSE Arca=AMEX.
# ⚠️ best-effort 매핑 — 모의투자에서 종목별 체결 확인하며 교정할 것.
_NYSE_SYMBOLS = {
    "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "C", "SCHW", "BLK", "AXP",
    "SPGI", "CB", "MMC", "PGR", "PNC", "USB", "TFC", "COF", "UNH", "JNJ", "LLY",
    "ABBV", "MRK", "TMO", "ABT", "DHR", "PFE", "BMY", "CVS", "MDT", "BSX", "BDX",
    "WMT", "PG", "KO", "MCD", "NKE", "HD", "LOW", "DIS", "XOM", "CVX", "COP", "SLB",
    "MPC", "PSX", "CAT", "DE", "HON", "GE", "RTX", "UNP", "UPS", "FDX", "BA", "LMT",
    "ETN", "ITW", "EMR", "NEE", "DUK", "SO", "LIN", "ORCL", "CRM", "IBM", "NOW", "ISRG",
}
_AMEX_SYMBOLS = {"SPY"}   # NYSE Arca 상장 ETF


def order_exchange(symbol: str) -> str:
    """심볼의 주문용 거래소코드(NASD/NYSE/AMEX). 미지정은 NASD."""
    s = symbol.upper()
    if s in _AMEX_SYMBOLS:
        return "AMEX"
    if s in _NYSE_SYMBOLS:
        return "NYSE"
    return "NASD"


def _tr(table: dict) -> str:
    mode = config.TRADING_MODE
    if mode not in table:
        raise ValueError(f"알 수 없는 KIS_TRADING_MODE: {mode}")
    return table[mode]


def _assert_trading_allowed() -> None:
    if config.TRADING_MODE == "prod" and os.getenv("ALLOW_PROD_TRADING", "").lower() != "true":
        raise RuntimeError(
            "실전투자(prod) 모드에서 해외주문이 차단되었습니다. "
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
def get_current_price(access_token: str, symbol: str, exchange: str | None = None) -> dict:
    """해외주식 현재가 조회. 반환: {"price": float 현재가}. 실패 시 예외."""
    exch = (exchange or order_exchange(symbol)).upper()
    params = {"AUTH": "", "EXCD": _PRICE_EXCD.get(exch, "NAS"), "SYMB": symbol.upper()}
    url = config.get_base_url() + PRICE_PATH
    resp = requests.get(url, headers=_headers(access_token, TR_PRICE), params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(f"해외 현재가 조회 오류 ({symbol}): {payload.get('msg1')}")
    out = payload.get("output", {})
    last = out.get("last") or out.get("ovrs_nmix_prpr")
    if not last:
        raise RuntimeError(f"해외 현재가 응답에 가격 없음 ({symbol}): {out}")
    return {"price": float(last)}


def limit_from_current(price: float, side: str) -> float:
    """현재가에 버퍼를 얹어 즉시체결용 지정가 산출 (미국 최소틱 0.01 반올림)."""
    buf = config.US_ORDER_SLIPPAGE
    px = price * (1 + buf) if side == "buy" else price * (1 - buf)
    return round(px, 2)


@retry_with_backoff(max_retries=2, base_delay=1.0, exceptions=(requests.RequestException,))
def _order_limit(access_token: str, symbol: str, qty: int, unit_price: float,
                 tr_id: str, exchange: str) -> dict:
    _assert_trading_allowed()
    cano, prdt = config._split_account()
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "OVRS_EXCG_CD": exchange,
        "PDNO": symbol.upper(),
        "ORD_QTY": str(int(qty)),
        "OVRS_ORD_UNPR": f"{unit_price:.2f}",
        "ORD_SVR_DVSN_CD": "0",
        "ORD_DVSN": "00",        # 지정가 (미국은 시장가 미지원)
    }
    url = config.get_base_url() + ORDER_PATH
    hashkey = _get_hashkey(body)
    resp = requests.post(url, headers=_headers(access_token, tr_id, hashkey), json=body, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(f"해외주문 실패 ({symbol} x{qty} @{unit_price}, {tr_id}): {payload.get('msg1')}")
    return payload.get("output", {})


def buy_limit(access_token: str, symbol: str, qty: int, current_price: float,
              exchange: str | None = None) -> dict:
    """현재가 기준 버퍼 얹은 지정가 매수."""
    exch = (exchange or order_exchange(symbol)).upper()
    unit = limit_from_current(current_price, "buy")
    logger.info("해외 지정가 매수: %s x%d @%.2f (%s)", symbol, qty, unit, exch)
    return _order_limit(access_token, symbol, qty, unit, _tr(_TR_BUY), exch)


def sell_limit(access_token: str, symbol: str, qty: int, current_price: float,
               exchange: str | None = None) -> dict:
    """현재가 기준 버퍼 뺀 지정가 매도."""
    exch = (exchange or order_exchange(symbol)).upper()
    unit = limit_from_current(current_price, "sell")
    logger.info("해외 지정가 매도: %s x%d @%.2f (%s)", symbol, qty, unit, exch)
    return _order_limit(access_token, symbol, qty, unit, _tr(_TR_SELL), exch)
