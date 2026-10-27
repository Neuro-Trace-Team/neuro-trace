from typing import Protocol, Dict, Any

class IResultPublisher(Protocol):
    async def publish_result(self, examination_id: str, result_payload: Dict[str, Any]) -> None:
        """Sends or publishes the inference result."""
        ...