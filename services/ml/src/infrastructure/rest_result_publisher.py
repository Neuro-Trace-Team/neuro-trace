import httpx
import logging
from typing import Any, Dict, Optional

from services.iresultpublisher import IResultPublisher


logger = logging.getLogger(__name__)

class RestResultPublisher(IResultPublisher):
    def __init__(self, base_url: str, auth_token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token

    async def publish_result(self, examination_id: str, result_payload: Dict[str, Any]) -> None:
        """Sends prediction results to a downstream REST endpoint via HTTP POST."""
        target_url = f"{self.base_url}/api/v1/examinations/{examination_id}/results"
        logger.info(f"Sending prediction result for examination {examination_id}...")

        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    target_url,
                    json=result_payload,
                    headers=headers,
                    timeout=10.0
                )

                response.raise_for_status()
                logger.info(f"Result successfully sent via REST. Status: {response.status_code}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to send result via REST (Status {e.response.status_code}): {e}")
                logger.error(f"Response body: {e.response.text}")
                raise
            except httpx.HTTPError as e:
                logger.error(f"Network or protocol error while sending result: {e}")
                raise