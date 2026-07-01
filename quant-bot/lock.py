"""동시 실행 방지 파일 락. 스케줄러가 이전 실행이 끝나기 전에 다시 트리거해도
API 호출이 겹쳐 rate limit을 넘기지 않도록 한다."""
import contextlib
import fcntl

import config

LOCK_PATH = config.BASE_DIR / ".collector.lock"


@contextlib.contextmanager
def single_instance_lock():
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        raise RuntimeError(f"이미 실행 중인 수집 작업이 있어 이번 실행은 건너뜁니다 (lock: {LOCK_PATH})")

    try:
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
