import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from core.config import settings
from core.logger import setup_logging
from event_handlers.ievent_handler import IEventHandler
from event_handlers.prediction_event_handler import PredictionEventHandler
from fastapi.responses import JSONResponse
from infrastructure.backend_auth_client import BackendAuthClient
from infrastructure.rabbit_mq_consumer import RabbitMQConsumer
from services.ipredictor import IPredictor
from infrastructure.rest_result_publisher import RestResultPublisher
from services.sklearn_predictor import SklearnPredictor

# Logger setup
setup_logging()
logger = logging.getLogger(__name__)


auth_client = BackendAuthClient(
    base_url=settings.backend_base_url,
    email=settings.backend_email,
    password=settings.backend_password
)
result_publisher = RestResultPublisher(
    base_url=settings.backend_base_url, 
    auth_client=auth_client
)

predictor: IPredictor = SklearnPredictor(model_path=settings.model_path)

consumer_task = None
rabbit_consumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task, rabbit_consumer

    logger.info("Starting up the ML Microservice...")

    # 1. Prediction model loading
    try:
        predictor.load_model()
    except Exception as e:
        logger.critical(f"Failed to load the ML model on startup: {e}")
        raise e

    # 2. Handlers definition
    prediction_handler = PredictionEventHandler(
        predictor=predictor,
        result_publisher=result_publisher
    )
    handlers_registry: dict[str, IEventHandler] = {
        "predict_event": prediction_handler
    }

    # 3. RabbitMQ setup
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
    return {
        "app_name": settings.app_name, 
        "model_path": settings.model_path
    }

@app.get("/healthz")
async def healthz():
    """Liveness probe for container orchestration."""
    return {
        "status": "healthy"
    }

@app.get("/readyz")
async def readyz():
    """Readiness probe."""
    # TODO: Add additional checks
    if not predictor.has_model():
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready", 
                "reason": "model_not_loaded"
            }
        )
    return {
        "status": "ready"
    }