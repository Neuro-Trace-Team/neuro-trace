from uuid import UUID
import httpx
from src.config import get_settings

class MLServiceError(RuntimeError): pass
class MLClient:
    def results(self, examination_id: UUID) -> dict:
        try:
            response = httpx.get(f"{get_settings().ml_url.rstrip('/')}/api/v1/examinations/{examination_id}/results", timeout=get_settings().service_timeout_seconds); response.raise_for_status(); value = response.json()
        except (httpx.HTTPError, ValueError) as error: raise MLServiceError("ML service is unavailable") from error
        if not isinstance(value, dict) or value.get("examination_id") != str(examination_id) or not isinstance(value.get("analyses"), list): raise MLServiceError("ML service returned an invalid results response")
        return value
