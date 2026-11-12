from typing import Any
from uuid import UUID

import httpx

from src.config import get_settings
from src.services.examinations import milliseconds_to_timestamp


class MLServiceError(RuntimeError):
    pass


def _is_non_boolean_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class MLClient:
    def results(self, examination_id: UUID) -> dict:
        try:
            response = httpx.get(
                f"{get_settings().ml_url.rstrip('/')}/examinations/{examination_id}/analyses",
                timeout=get_settings().service_timeout_seconds,
            )
            value = response.json()
            if response.status_code == httpx.codes.ACCEPTED:
                return self._processing_results(examination_id, value)
            response.raise_for_status()
        except (httpx.HTTPError, ValueError) as error:
            raise MLServiceError("ML service is unavailable") from error

        if (
            not isinstance(value, dict)
            or value.get("examination_id") != str(examination_id)
            or not _is_non_boolean_int(value.get("total_analyses_count"))
            or value["total_analyses_count"] < 0
            or not isinstance(value.get("analyses"), list)
        ):
            raise MLServiceError("ML service returned an invalid results response")
        analyses = []
        for analysis in value["analyses"]:
            if (
                not isinstance(analysis, dict)
                or not _is_non_boolean_int(analysis.get("analysis_id"))
                or not isinstance(analysis.get("time_stamp"), (int, float))
                or isinstance(analysis["time_stamp"], bool)
                or not isinstance(analysis.get("is_valid"), bool)
                or "result" not in analysis
                or (
                    analysis["result"] is not None
                    and (
                        not isinstance(analysis["result"], (int, float))
                        or isinstance(analysis["result"], bool)
                    )
                )
                or (
                    analysis.get("invalid_reason") is not None
                    and not isinstance(analysis["invalid_reason"], str)
                )
                or (
                    analysis.get("confidence") is not None
                    and (
                        not isinstance(analysis["confidence"], (int, float))
                        or isinstance(analysis["confidence"], bool)
                    )
                )
            ):
                raise MLServiceError("ML service returned an invalid analysis")
            try:
                frontend_timestamp = milliseconds_to_timestamp(analysis["time_stamp"])
            except ValueError as error:
                raise MLServiceError("ML returned an invalid timestamp in milliseconds") from error
            analyses.append({**analysis, "time_stamp": frontend_timestamp})
        return {"status": "READY", **value, "analyses": analyses}

    @staticmethod
    def _processing_results(examination_id: UUID, value: Any) -> dict:
        if (
            not isinstance(value, dict)
            or value.get("status") != "processing"
            or not _is_non_boolean_int(value.get("received"))
            or not _is_non_boolean_int(value.get("expected"))
            or value["received"] < 0
            or value["expected"] < 0
            or value["received"] > value["expected"]
        ):
            raise MLServiceError("ML service returned an invalid processing response")
        return {
            "status": "PROCESSING",
            "examination_id": str(examination_id),
            "received_analyses_count": value["received"],
            "total_analyses_count": value["expected"],
            "analyses": [],
        }
