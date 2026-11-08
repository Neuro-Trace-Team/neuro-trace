from typing import Protocol, Dict, Any

class IEventHandler(Protocol):
    async def handle(self, payload: Dict[str, Any]) -> None:
        """Handles the incoming message payload."""
        ...