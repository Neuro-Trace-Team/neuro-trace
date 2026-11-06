class BackendAuthClient:
    """Provide the pre-issued bearer token used by backend service clients."""

    def __init__(self, service_token: str) -> None:
        self.service_token = service_token.strip()

    async def get_token(self) -> str:
        if not self.service_token:
            raise RuntimeError("ML_SERVICE_TOKEN is not configured")
        return self.service_token

    async def invalidate_token(self) -> None:
        # Service tokens are static for the lifetime of this process. A 401
        # requires token rotation in the deployment environment.
        return None
