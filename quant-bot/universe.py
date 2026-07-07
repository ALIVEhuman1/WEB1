"""코스피/코스닥 전 종목 리스트 조회 (FinanceDataReader 기반).

동적 watchlist의 모집단. 보통주만 남기기 위해 우선주(종목코드 끝자리 0이 아님),
스팩주는 제외한다.
"""
import logging

logger = logging.getLogger(__name__)

MARKETS = ("KOSPI", "KOSDAQ")


def get_universe() -> list[str]:
    """코스피+코스닥 보통주 종목코드 리스트."""
    import FinanceDataReader as fdr

    listing = fdr.StockListing("KRX")

    codes = []
    for _, row in listing.iterrows():
        code = str(row["Code"]).zfill(6)
        market = str(row.get("Market", ""))
        name = str(row.get("Name", ""))

        if market not in MARKETS:
            continue
        if not code.endswith("0"):
            continue  # 우선주 등 제외 (보통주는 코드가 0으로 끝남)
        if "스팩" in name:
            continue
        codes.append(code)

    logger.info("유니버스: 코스피+코스닥 보통주 %d종목", len(codes))
    return codes
