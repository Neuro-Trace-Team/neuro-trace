import logging
from typing import Any, Dict

from event_handlers.ievent_handler import IEventHandler
from services.ipredictor import IPredictor
from services.iresultpublisher import IResultPublisher

logger = logging.getLogger(__name__)

class PredictionEventHandler(IEventHandler):
    def __init__(self, predictor: IPredictor, result_publisher: IResultPublisher) -> None:
        self.predictor = predictor
        self.result_publisher = result_publisher

    async def handle(self, payload: Dict[str, Any]) -> None:
        """Handles the incoming combined EEG features message."""

        experiment_id = payload.get("experiment_id")
        analysis_id = payload.get("analysis_id")
        subject_id = payload.get("subject_id")
        recording_id = payload.get("recording_id")
        window_id = payload.get("window_id")

        logger.info(
            f"Processing EEG event | Experiment: {experiment_id} | "
            f"Subject: {subject_id} | Recording: {recording_id} | Window: {window_id}"
        )

        try:
            if not analysis_id:
                raise ValueError("Incoming prediction event is missing analysis_id")

            metadata_keys = {
                "analysis_id", "experiment_id", "subject_id", "recording_id", "window_id",
                "event_id", "event_index", "event_time_s", "event_timestamp",
                "cluster_id", "cluster_event_time_s", "cluster_size", "overlap_flag"
            }

            feature_payload = {k: v for k, v in payload.items() if k not in metadata_keys}

            result = self.predictor.predict(feature_payload)

            logger.info(f"Inference successful for Recording {recording_id}: {result}")

            probabilities = result.get("probabilities")
            confidence = (
                max(probabilities[0])
                if probabilities and probabilities[0]
                else None
            )
            output_payload = {"result": result}
            if confidence is not None:
                output_payload["confidence"] = confidence

            await self.result_publisher.publish_result(analysis_id, output_payload)
        except Exception as e:
            logger.error(f"Failed to process prediction for Recording {recording_id}: {e}")
            raise e
