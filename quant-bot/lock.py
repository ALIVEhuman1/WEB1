"""동시 실행 방지 파일 락. 스케줄러가 이전 실행이 끝나기 전에 다시 트리거해도
API 호출이 겹쳐 rate limit을 넘기지 않도록 한다."""
import contextlib
import fcntl

import config


@contextlib.contextmanager
def single_instance_lock(name: str = "collector"):
    lock_path = config.BASE_DIR / f".{name}.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        raise RuntimeError(f"이미 실행 중인 {name} 작업이 있어 이번 실행은 건너뜁니다 (lock: {lock_path})")

    try:
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
