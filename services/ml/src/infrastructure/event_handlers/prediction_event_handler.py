import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import math
from typing import Any, Dict
from uuid import UUID

from domain.entities.analysis import NewAnalysis
from domain.repositories.ianalysis_repository import IAnalysisRepository
from domain.services.ieventpublisher import IEventPublisher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.event_handlers.ievent_handler import IEventHandler
from domain.services.ipredictor import FeatureValidationError, IPredictor


@dataclass(frozen=True)
class Evaluation:
    result: float | None = None
    confidence: float | None = None
    invalid_reason: str | None = None

RepositoryFactory = Callable[[AsyncSession], IAnalysisRepository]

RESULT_MIN, RESULT_MAX = 0.0, 10.0

METADATA_KEYS = frozenset({
    "experiment_id", "subject_id", "recording_id", "window_id",
    "event_id", "event_index", "event_time_s", "event_timestamp",
    "cluster_id", "cluster_event_time_s", "cluster_size", "overlap_flag",
    "total_analyses_count", "examination_id",
})

logger = logging.getLogger(__name__)

class PredictionEventHandler(IEventHandler):
    def __init__(
            self, 
            predictor: IPredictor, 
            session_factory: async_sessionmaker[AsyncSession], 
            event_publisher: IEventPublisher,
            repository_factory: RepositoryFactory,
        ) -> None:
        self.predictor = predictor
        self.session_factory = session_factory
        self.event_publisher = event_publisher
        self.repository_factory = repository_factory

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
            examination_id, event_timestamp, total = self._parse_envelope(payload)
            feature_payload = {k: v for k, v in payload.items() if k not in METADATA_KEYS}
            
            evaluation = await self._evaluate(feature_payload)

            new = NewAnalysis(
                examination_id=examination_id,
                event_timestamp=event_timestamp,
                result=evaluation.result,
                confidence=evaluation.confidence,
                total_analyses_count=total,
                is_valid=evaluation.invalid_reason is None,
                invalid_reason=evaluation.invalid_reason,
            )

            async with self.session_factory() as session, session.begin():
                repo = self.repository_factory(session)
                await repo.lock_examination(examination_id)
                saved = await repo.add(new)
                received = await repo.count_for_examination(examination_id)

                if (saved.total_analyses_count, saved.is_valid) != (new.total_analyses_count, new.is_valid):
                    logger.warning(
                        "Conflicting duplicate for examination %s at t=%s: stored total=%s valid=%s, "
                        "received total=%s valid=%s; keeping the stored row",
                        examination_id, event_timestamp, saved.total_analyses_count, saved.is_valid,
                        new.total_analyses_count, new.is_valid,
                    )

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

        except Exception:
            logger.exception(f"Failed to process prediction for Recording {recording_id}")
            raise

    @staticmethod
    def _parse_envelope(payload) -> tuple[UUID, float, int]:
        require = PredictionEventHandler._require
        examination_id = UUID(str(require(payload, "examination_id")))

        event_timestamp = float(require(payload, "event_time_s"))
        if not math.isfinite(event_timestamp) or event_timestamp < 0:
            raise ValueError("event_time_s must be a finite, non-negative number")
        
        total = int(require(payload, "total_analyses_count"))
        if total < 1:
            raise ValueError("total_analyses_count must be >= 1")
        
        return examination_id, event_timestamp, total

    async def _evaluate(self, features: dict[str, Any]) -> Evaluation:
        """Never raises: any failure becomes an invalid analysis, so the examination can complete."""
        try:
            prediction = await asyncio.to_thread(self.predictor.predict, features)
        except FeatureValidationError as e:
            logger.warning("Invalid input features: %s", e)
            return Evaluation(invalid_reason=self._describe(e))
        except Exception:
            logger.exception("Prediction failed")
            return Evaluation(invalid_reason="prediction_failed")

        try:
            result = self._extract_result(prediction)
            confidence = self._extract_confidence(prediction)
        except (KeyError, IndexError, TypeError, ValueError):
            logger.exception("Unusable model output: %r", prediction)
            return Evaluation(invalid_reason="unusable_model_output")

        if not RESULT_MIN <= result <= RESULT_MAX:
            return Evaluation(invalid_reason=f"result_out_of_range: {result}")
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            logger.warning("Dropping out-of-range confidence %r", confidence)
            confidence = None
        return Evaluation(result, confidence)

    @staticmethod
    def _describe(error: FeatureValidationError) -> str:
        def preview(names, limit=10):
            extra = f" (+{len(names) - limit} more)" if len(names) > limit else ""
            return ", ".join(names[:limit]) + extra

        parts = []
        if error.missing:
            parts.append(f"missing_features: {preview(error.missing)}")
        if error.invalid:
            parts.append(f"invalid_feature_values: {preview(error.invalid)}")
        return "; ".join(parts) or "feature_validation_failed"

    @staticmethod
    def _require(payload: Dict[str, Any], key: str) -> Any:
        value = payload.get(key)
        if value is None:
            raise ValueError(f"Incoming prediction event is missing {key}")
        return value

    @staticmethod
    def _extract_result(result: Dict[str, Any]) -> float:
        return float(result["prediction"][0])

    @staticmethod
    def _extract_confidence(result: Dict[str, Any]) -> float | None:
        probabilities = result.get("probabilities")
        return float(max(probabilities[0])) if probabilities and probabilities[0] else None
