import httpx
import logging
from typing import Any, Dict, Optional

from infrastructure.backend_auth_client import BackendAuthClient
from services.iresultpublisher import IResultPublisher


logger = logging.getLogger(__name__)

class RestResultPublisher(IResultPublisher):
    def __init__(self, base_url: str, auth_client: BackendAuthClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_client = auth_client

    async def publish_result(self, analysis_id: str, result_payload: Dict[str, Any]) -> None:
        """Send a completed prediction to the backend analysis callback."""
        target_url = f"{self.base_url}/api/v1/internal/analyses/{analysis_id}/result"
        logger.info("Sending prediction result for analysis %s...", analysis_id)

        async with httpx.AsyncClient() as client:
            token = await self.auth_client.get_token()
            headers = {"Authorization": f"Bearer {token}"}
            try:
                response = await client.post(
                    target_url,
                    json=result_payload,
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.info("Result successfully sent via REST. Status: %s", response.status_code)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Backend rejected ML result (status %s): %s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise
            except httpx.HTTPError:
                logger.exception("Network or protocol error while sending result")
                raise
