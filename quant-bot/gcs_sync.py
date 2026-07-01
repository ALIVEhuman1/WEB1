"""Cloud Run Job처럼 실행마다 컨테이너가 초기화되는 환경에서 SQLite DB를 보존하기 위한
GCS 백업/복원. GCS_BUCKET_NAME이 설정된 경우에만 동작하고, 없으면 아무 것도 하지 않는다
(상시 실행되는 VM 환경에서는 로컬 디스크만으로 충분하므로)."""
import logging
import os

import config

logger = logging.getLogger(__name__)

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_DB_BLOB_NAME = os.getenv("GCS_DB_BLOB_NAME", "candles.db")


def _get_bucket():
    from google.cloud import storage

    client = storage.Client()
    return client.bucket(GCS_BUCKET_NAME)


def download_db() -> None:
    """실행 시작 시 GCS에 저장된 최신 DB를 로컬로 내려받는다."""
    if not GCS_BUCKET_NAME:
        return
    blob = _get_bucket().blob(GCS_DB_BLOB_NAME)
    if blob.exists():
        blob.download_to_filename(config.DB_PATH)
        logger.info("GCS에서 DB 복원: gs://%s/%s -> %s", GCS_BUCKET_NAME, GCS_DB_BLOB_NAME, config.DB_PATH)
    else:
        logger.info("GCS에 기존 DB 없음 (최초 실행으로 판단, 새 DB 생성)")


def upload_db() -> None:
    """실행 종료 시 로컬 DB를 GCS에 업로드해 다음 실행에서도 데이터가 이어지게 한다."""
    if not GCS_BUCKET_NAME:
        return
    blob = _get_bucket().blob(GCS_DB_BLOB_NAME)
    blob.upload_from_filename(config.DB_PATH)
    logger.info("GCS에 DB 백업: %s -> gs://%s/%s", config.DB_PATH, GCS_BUCKET_NAME, GCS_DB_BLOB_NAME)
