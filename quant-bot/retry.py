"""API 호출 실패 시 최대 N회, 지수 백오프로 재시도하는 공용 데코레이터."""
import functools
import time


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt > max_retries:
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    print(f"[retry] {func.__name__} 실패 ({attempt}/{max_retries}): {exc} -> {delay:.1f}초 후 재시도")
                    time.sleep(delay)
        return wrapper
    return decorator
