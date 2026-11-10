from uuid import UUID
import httpx
from src.config import get_settings

class PreprocessingServiceError(RuntimeError): pass
class PreprocessingClient:
    def _url(self, path: str) -> str: return f"{get_settings().preprocessing_url.rstrip('/')}{path}"
    def request(self, examination_id: UUID, storage_bucket: str, storage_key: str) -> None:
        try:
            response = httpx.post(self._url(f"/api/v1/examinations/{examination_id}/preprocessing"), json={"examination_id": str(examination_id), "storage_bucket": storage_bucket, "storage_key": storage_key}, timeout=get_settings().service_timeout_seconds); response.raise_for_status()
        except httpx.HTTPError as error: raise PreprocessingServiceError("Preprocessing service is unavailable or rejected the request") from error
    def status(self, examination_id: UUID) -> dict:
        try:
            response = httpx.get(self._url(f"/api/v1/examinations/{examination_id}/preprocessing-status"), timeout=get_settings().service_timeout_seconds); response.raise_for_status(); value = response.json()
        except (httpx.HTTPError, ValueError) as error: raise PreprocessingServiceError("Preprocessing status is unavailable") from error
        if not isinstance(value, dict) or value.get("examination_id") != str(examination_id) or not isinstance(value.get("status"), str): raise PreprocessingServiceError("Preprocessing service returned an invalid status response")
        return value
