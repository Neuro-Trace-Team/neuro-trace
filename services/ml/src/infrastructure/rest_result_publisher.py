import httpx
import logging
from typing import Any, Dict

from services.iresultpublisher import IResultPublisher


logger = logging.getLogger(__name__)

class RestResultPublisher(IResultPublisher):
    def __init__(self, target_url: str) -> None:
        self.target_url = target_url

    async def publish_result(self, result_payload: Dict[str, Any]) -> None:
        """Sends prediction results to a downstream REST endpoint via HTTP POST."""
        logger.info(f"Sending prediction result via REST to {self.target_url}...")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.target_url,
                    json=result_payload,
                    timeout=10.0
                )

                response.raise_for_status()
                logger.info(f"Result successfully sent via REST. Status: {response.status_code}")
            except httpx.HTTPError as e:
                logger.error(f"Failed to send result via REST: {e}")
                raise e