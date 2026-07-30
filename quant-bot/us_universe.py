"""US RSI(2) 백테스트용 유니버스: S&P 500 유동성 상위 대형주 ~100종목.

위키 스크래핑 등 외부 의존을 피하려고 하드코딩한다 (1GB VM 안정성). 정확한
구성종목 편입/편출보다 '유동성 큰 대형주 표본'이 목적이라 고정 리스트로 충분하다.
ETF/우선주는 포함하지 않는다. yfinance 티커 표기 기준 (예: 버크셔 = BRK-B).
"""

_TICKERS = [
    # 메가캡 테크/성장
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "TSLA", "AVGO", "ORCL",
    "ADBE", "CRM", "AMD", "INTC", "CSCO", "QCOM", "TXN", "IBM", "NOW", "INTU",
    "AMAT", "MU", "LRCX", "KLAC", "SNPS", "CDNS", "ADI", "NXPI", "MRVL", "PANW",
    # 금융
    "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "C", "SCHW",
    "BLK", "AXP", "SPGI", "CB", "MMC", "PGR", "PNC", "USB", "TFC", "COF",
    # 헬스케어
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "PFE", "BMY",
    "AMGN", "GILD", "ISRG", "VRTX", "REGN", "CVS", "MDT", "BSX", "ZTS", "BDX",
    # 소비/산업/에너지/기타
    "WMT", "PG", "KO", "PEP", "COST", "MCD", "NKE", "HD", "LOW", "SBUX",
    "TJX", "BKNG", "MAR", "DIS", "CMCSA", "NFLX", "XOM", "CVX", "COP", "SLB",
    "EOG", "MPC", "PSX", "CAT", "DE", "HON", "GE", "RTX", "UNP", "UPS",
    "FDX", "BA", "LMT", "ETN", "ITW", "EMR", "NEE", "DUK", "SO", "LIN",
]


def load_us_universe() -> list[str]:
    """중복 제거된 티커 리스트를 반환한다."""
    seen, out = set(), []
    for t in _TICKERS:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
