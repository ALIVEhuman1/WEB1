"""KIS API 초당 20건 제한을 지키기 위한 배치 크기 / 딜레이 자동 계산.

실제 한도(20건/초)보다 여유를 두고 보수적으로 설정해, 네트워크 지연이나
버스트 호출로 인한 초과를 방지한다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BatchPlan:
    batch_size: int      # 한 배치에서 동시에 처리할 종목 수
    call_delay: float    # 개별 API 호출 사이의 딜레이(초) - 페이지네이션 호출에도 동일 적용
    batch_delay: float   # 배치와 배치 사이의 추가 딜레이(초)


def get_batch_plan(num_stocks: int) -> BatchPlan:
    if num_stocks <= 20:
        return BatchPlan(batch_size=10, call_delay=0.15, batch_delay=1.0)
    elif num_stocks <= 50:
        return BatchPlan(batch_size=5, call_delay=0.2, batch_delay=1.5)
    else:
        return BatchPlan(batch_size=3, call_delay=0.3, batch_delay=2.0)


def chunk(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]
