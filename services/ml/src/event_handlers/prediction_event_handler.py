from typing import Any, Dict

from services.ml.src.services.ipredictor import IPredictor


class PredictionEventHandler:
    def __init__(self, predictor: IPredictor) -> None:
        self.predictor = predictor

    async def handle(self, payload: Dict[str, Any]) -> None:
        """Processes the prediction event."""
        # TODO: get features from payload

        # TODO: perform ML prediction

        # TODO: publish result? or should it be handled somewhere else?
        