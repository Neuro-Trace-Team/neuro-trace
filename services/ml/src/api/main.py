import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request

from core.config import settings
from core.logger import setup_logging
from infrastructure.db.session import create_engine, create_session_factory
from infrastructure.event_handlers.ievent_handler import IEventHandler
from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler
from fastapi.responses import JSONResponse
from infrastructure.messaging.rabbit_mq_consumer import RabbitMQConsumer
from domain.services.ipredictor import IPredictor
from infrastructure.messaging.rabbit_mq_publisher import RabbitMQPublisher
from infrastructure.repositories.sql_alchemy_analysis_repository import SqlAlchemyAnalysisRepository
from infrastructure.services.sklearn_predictor import SklearnPredictor
from api.routes.analyses import router as analyses_router
from sqlalchemy import text


READINESS_DB_TIMEOUT_S = 2


def _log_consumer_exit(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        logger.critical("RabbitMQ consumer stopped unexpectedly", exc_info=task.exception())

# Logger setup
setup_logging()
logger = logging.getLogger(__name__)

predictor: IPredictor = SklearnPredictor(model_path=settings.model_path, require_feature_names=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the ML Microservice...")

    try:
        predictor.load_model()
    except Exception:
        logger.critical(f"Failed to load the ML model on startup", exc_info=True)
        raise

    engine = create_engine(settings.database_url)
    publisher = RabbitMQPublisher(settings.queue_url, settings.completed_queue_name)
    rabbit_consumer = None
    consumer_task = None

    try:
        session_factory = create_session_factory(engine)
        app.state.engine = engine
        app.state.session_factory = session_factory

        await publisher.connect()

        handler = PredictionEventHandler(
            predictor=predictor,
            session_factory=session_factory,
            event_publisher=publisher,
            repository_factory=SqlAlchemyAnalysisRepository,
        )

        rabbit_consumer = RabbitMQConsumer(
            queue_url=settings.queue_url,
            queue_name=settings.pending_analysis_queue_name,
            handlers={"predict_event": handler},
        )

        consumer_task = asyncio.create_task(rabbit_consumer.start())
        consumer_task.add_done_callback(_log_consumer_exit)
        app.state.consumer_task = consumer_task

        yield
    finally:
        logger.info("Shutting down the ML Microservice...")
    
        if consumer_task:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                logger.info("Background consumer task successfully cancelled.")
            except Exception:
                logger.exception("Consumer task had already failed.")
            
        if rabbit_consumer:
            await rabbit_consumer.close()

        await publisher.close()   

        await engine.dispose()

        logger.info("Microservice shutdown complete.")

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan
)
app.include_router(analyses_router)

async def _ping_db(engine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

@app.get("/info")
async def info():
    return {
        "app_name": settings.app_name,
        "model": predictor.model_info() 
    }

@app.get("/healthz")
async def healthz():
    """Liveness probe for container orchestration."""
    return {
        "status": "healthy"
    }

@app.get("/readyz")
async def readyz(request: Request):
    """Readiness probe."""
    if not predictor.has_model():
        logger.warning("Readiness check: model not ready", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready", 
                "reason": "model_not_loaded"
            }
        )

    task = getattr(request.app.state, "consumer_task", None)
    if task is None or task.done():
        return JSONResponse(
            status_code=503, 
            content={
                "status": "not_ready", 
                "reason": "consumer_not_running"
            }
        )
    
    try:
        await asyncio.wait_for(_ping_db(request.app.state.engine), READINESS_DB_TIMEOUT_S)
    except Exception:
        logger.warning("Readiness check: database unreachable", exc_info=True)
        return JSONResponse(
            status_code=503, 
            content={
                "status": "not_ready", 
                "reason": "database_unavailable"
                }
            )
    
    return {"status": "ready"}
