import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from services.ml.src.core.config import settings
from services.ml.src.core.logger import setup_logging
from services.ml.src.event_handlers.ievent_handler import IEventHandler
from services.ml.src.event_handlers.prediction_event_handler import PredictionEventHandler
from services.ml.src.infrastructure.rabbit_mq_consumer import RabbitMQConsumer
from services.ml.src.models.ipredictor import IPredictor

setup_logging()
logger = logging.getLogger(__name__)

predictor: IPredictor = None
consumer_task = None
rabbit_consumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task, rabbit_consumer

    logger.info("Starting up the ML Microservice...")

    try:
        predictor.load_model()
    except Exception as e:
        logger.critical(f"Failed to load the ML model on startup: {e}")
        raise e

    prediction_handler = PredictionEventHandler(predictor=predictor)
    handlers_registry: dict[str, IEventHandler] = {
        "predict_event": prediction_handler
    }

    rabbit_consumer = RabbitMQConsumer(
        queue_url=settings.queue_url,
        queue_name=settings.queue_name,
        handlers=handlers_registry
    )

    logger.info("Creating background RabbitMQ consumer task...")
    consumer_task = asyncio.create_task(rabbit_consumer.start())

    yield

    logger.info("Shutting down the ML Microservice...")
    
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("Background consumer task successfully cancelled.")
            
    if rabbit_consumer:
        await rabbit_consumer.close()
        
    logger.info("Microservice shutdown complete.")

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan
)

@app.get("/info")
async def info():
    return {"app_name": settings.app_name, "model_path": settings.model_path}

@app.get("/healthz")
async def healthz():
    """Liveness probe for container orchestration."""
    return {"status": "healthy"}

@app.get("/readyz")
async def readyz():
    """Readiness probe."""
    # TODO: Add actual checks
    if not predictor.has_model():
        return {"status": "not_ready", "reason": "model_not_loaded"}, 503
    return {"status": "ready"}