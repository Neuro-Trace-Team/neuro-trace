from typing import Any, Dict

from services.ml.src.event_handlers.ievent_handler import IEventHandler
from services.ml.src.services.iprediction_service import IPredictionService


class PredictionEventHandler(IEventHandler):
    def __init__(self, predictor: IPredictionService) -> None:
        self.predictor = predictor

    async def handle(self, payload: Dict[str, Any]) -> None:
        """Processes the prediction event."""
        # TODO: get features from payload

        # TODO: perform ML prediction

        # TODO: publish result? or should it be handled somewhere else?
        