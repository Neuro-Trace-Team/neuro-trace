import logging
from typing import Optional

import httpx


logger = logging.getLogger(__name__)

class BackendAuthClient:
    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self._access_token: Optional[str] = None

    async def get_token(self) -> Optional[str]:
        """Fetches a fresh access token or reuses the cached one."""
        if self._access_token:
            logger.debug("Reusing cached access token.")
            return self._access_token

        login_url = f"{self.base_url}/api/v1/auth/login"
        logger.info("Attempting to fetch a fresh access token from %s", login_url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    login_url,
                    json={
                        "email": self.email, 
                        "password": self.password
                    }, 
                    timeout=10.0
                )
                response.raise_for_status()

                data = response.json()

                self._access_token = data["access_token"]
                logger.info("Successfully obtained and cached new access token.")
                
                return self._access_token

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching token: status_code={e.response.status_code}, response={e.response.text}")
            raise
        except Exception as e:
            logger.exception("Unexpected error occurred while fetching token: %s", e)
            raise

    async def invalidate_token(self) -> Optional[str]:
        logger.debug("Invalidating cached access token.")
        self._access_token = None