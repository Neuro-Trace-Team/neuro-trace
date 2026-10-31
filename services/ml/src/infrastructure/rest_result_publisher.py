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

    async def publish_result(self, examination_id: str, result_payload: Dict[str, Any]) -> None:
        """Sends prediction results to a downstream REST endpoint via HTTP POST."""
        target_url = f"{self.base_url}/api/v1/examinations/{examination_id}/results"
        logger.info(f"Sending prediction result for examination {examination_id}...")

        async with httpx.AsyncClient() as client:
            for attempt in range(2):
                token = await self.auth_client.get_token()
                headers = {"Authorization": f"Bearer {token}"}

                try:
                    response = await client.post(
                        target_url,
                        json=result_payload,
                        headers=headers,
                        timeout=10.0
                    )

                    response.raise_for_status()
                    logger.info(f"Result successfully sent via REST. Status: {response.status_code}")
                    return
                
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401 and attempt == 0:
                        logger.warning("Received 401 Unauthorized. Invalidating token and retrying...")
                        await self.auth_client.invalidate_token()
                        continue
                    
                    logger.error(f"Failed to send result via REST (Status {e.response.status_code}): {e}")
                    logger.error(f"Response body: {e.response.text}")
                    raise
                except httpx.HTTPError as e:
                    logger.error(f"Network or protocol error while sending result: {e}")
                    raise