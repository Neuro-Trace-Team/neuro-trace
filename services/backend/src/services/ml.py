from uuid import UUID
import httpx
from src.config import get_settings

class MLServiceError(RuntimeError): pass
class MLClient:
    def results(self, examination_id: UUID) -> dict:
        try:
            response = httpx.get(f"{get_settings().ml_url.rstrip('/')}/examinations/{examination_id}/analyses", timeout=get_settings().service_timeout_seconds); response.raise_for_status(); value = response.json()
        except (httpx.HTTPError, ValueError) as error: raise MLServiceError("ML service is unavailable") from error
        if not isinstance(value, dict) or value.get("examination_id") != str(examination_id) or not isinstance(value.get("total_analyses_count"), int) or isinstance(value["total_analyses_count"], bool) or value["total_analyses_count"] < 0 or not isinstance(value.get("analyses"), list): raise MLServiceError("ML service returned an invalid results response")
        for analysis in value["analyses"]:
            if not isinstance(analysis, dict) or not isinstance(analysis.get("analysis_id"), int) or isinstance(analysis["analysis_id"], bool) or not isinstance(analysis.get("time_stamp"), (int, float)) or isinstance(analysis["time_stamp"], bool) or not isinstance(analysis.get("result"), (int, float)) or isinstance(analysis["result"], bool) or (analysis.get("confidence") is not None and (not isinstance(analysis["confidence"], (int, float)) or isinstance(analysis["confidence"], bool))):
                raise MLServiceError("ML service returned an invalid analysis")
        return value
