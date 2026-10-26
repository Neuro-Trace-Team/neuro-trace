import logging
from typing import Any, Dict

from services.ml.src.event_handlers.ievent_handler import IEventHandler
from services.ml.src.models.ipredictor import IPredictor

logger = logging.getLogger(__name__)

class PredictionEventHandler(IEventHandler):
    def __init__(self, predictor: IPredictor) -> None:
        self.predictor = predictor

    async def handle(self, payload: Dict[str, Any]) -> None:
        """Handles the incoming combined EEG features message."""

        experiment_id = payload.get("experiment_id")
        subject_id = payload.get("subject_id")
        recording_id = payload.get("recording_id")
        window_id = payload.get("window_id")

        logger.info(
            f"Processing EEG event | Experiment: {experiment_id} | "
            f"Subject: {subject_id} | Recording: {recording_id} | Window: {window_id}"
        )

        try:
            metadata_keys = {
                "experiment_id", "subject_id", "recording_id", "window_id", 
                "event_id", "event_index", "event_time_s", "event_timestamp",
                "cluster_id", "cluster_event_time_s", "cluster_size", "overlap_flag"
            }

            feature_payload = {k: v for k, v in payload.items() if k not in metadata_keys}

            result = self.predictor.predict(feature_payload)

            logger.info(f"Inference successful for Recording {recording_id}: {result}")

            # TODO: Publish result or send it directly to the backend
        except Exception as e:
            logger.error(f"Failed to process prediction for Recording {recording_id}: {e}")
            raise e
        