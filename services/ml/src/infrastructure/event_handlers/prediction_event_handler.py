import asyncio
import logging
from typing import Any, Dict
from uuid import UUID

from domain.entities.analysis import NewAnalysis
from domain.services.ieventpublisher import IEventPublisher
from infrastructure.repositories.sql_alchemy_analysis_repository import SqlAlchemyAnalysisRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.event_handlers.ievent_handler import IEventHandler
from domain.services.ipredictor import IPredictor
from domain.services.iresultpublisher import IResultPublisher


metadata_keys = {
    "analysis_id", "experiment_id", "subject_id", "recording_id", "window_id",
    "event_id", "event_index", "event_time_s", "event_timestamp",
    "cluster_id", "cluster_event_time_s", "cluster_size", "overlap_flag", "total_events", "examination_id"
}

logger = logging.getLogger(__name__)

class PredictionEventHandler(IEventHandler):
    def __init__(self, predictor: IPredictor, session_factory: async_sessionmaker[AsyncSession], event_publisher: IEventPublisher) -> None:
        self.predictor = predictor
        self.session_factory = session_factory
        self.event_publisher = event_publisher

    async def handle(self, payload: Dict[str, Any]) -> None:
        """Handles the incoming combined EEG features message."""

        # TODO: VERIFY HOW IS THE JSON GONNA LOOK AND WHAT CAN I USE
        experiment_id = payload.get("experiment_id")
        subject_id = payload.get("subject_id")
        recording_id = payload.get("recording_id")
        window_id = payload.get("window_id")

        logger.info(
            f"Processing EEG event | Experiment: {experiment_id} | "
            f"Subject: {subject_id} | Recording: {recording_id} | Window: {window_id}"
        )

        try:
            examination_id = UUID(str(self._require(payload, "examination_id")))
            event_timestamp = float(self._require(payload, "event_time_s"))
            total = int(self._require(payload, "total_events"))

            feature_payload = {k: v for k, v in payload.items() if k not in metadata_keys}
            result = await asyncio.to_thread(self.predictor.predict, feature_payload)

            new = NewAnalysis(
                examination_id=examination_id,
                event_timestamp=event_timestamp,
                result=self._extract_result(result),
                confidence=self._extract_confidence(result),
                total_analyses_count=total,
            )

            async with self.session_factory() as session, session.begin():
                repo = SqlAlchemyAnalysisRepository(session)
                await repo.lock_examination(examination_id)
                saved = await repo.add(new)
                received = await repo.count_for_examination(examination_id)

            if received >= saved.total_analyses_count:
                await self.event_publisher.publish(
                    "examination_completed",
                    {
                        "examination_id": examination_id,
                        "total_analyses_count": saved.total_analyses_count,
                    },
                )

            logger.info(f"Stored analysis {saved.analysis_id} for examination {examination_id} "
                        f"at t={event_timestamp}s")

        except Exception as e:
            logger.exception(f"Failed to process prediction for Recording {recording_id}")
            raise

    @staticmethod
    def _require(payload: Dict[str, Any], key: str) -> Any:
        value = payload.get(key)
        if value is None:
            raise ValueError(f"Incoming prediction event is missing {key}")
        return value

    @staticmethod
    def _extract_result(result: Dict[str, Any]) -> float:
        return float(result["prediction"])

    @staticmethod
    def _extract_confidence(result: Dict[str, Any]) -> float | None:
        probabilities = result.get("probabilities")
        return float(max(probabilities[0])) if probabilities and probabilities[0] else None
