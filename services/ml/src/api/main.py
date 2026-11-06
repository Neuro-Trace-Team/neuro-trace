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
from infrastructure.clients.backend_auth_client import BackendAuthClient
from infrastructure.messaging.rabbit_mq_consumer import RabbitMQConsumer
from domain.services.ipredictor import IPredictor
from infrastructure.clients.rest_result_publisher import RestResultPublisher
from infrastructure.messaging.rabbit_mq_publisher import RabbitMQPublisher
from infrastructure.services.sklearn_predictor import SklearnPredictor
from api.routes.analyses import router as analyses_router
from sqlalchemy import text


# Logger setup
setup_logging()
logger = logging.getLogger(__name__)


auth_client = BackendAuthClient(
    service_token=settings.backend_service_token,
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

    # 2. Database objects
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    # 3. RabbitMQ Publisher setup
    event_publisher = RabbitMQPublisher(
        settings.queue_url,
        settings.completed_queue_name
    )
    logger.info("Creating RabbitMQ publisher service...")
    await event_publisher.connect()

    # 4. Handlers definition
    prediction_handler = PredictionEventHandler(
        predictor=predictor,
        session_factory=session_factory,
        event_publisher=event_publisher
    )
    handlers_registry: dict[str, IEventHandler] = {
        "predict_event": prediction_handler
    }

    # 5. RabbitMQ Consumer setup
    rabbit_consumer = RabbitMQConsumer(
        queue_url=settings.queue_url,
        queue_name=settings.pending_analysis_queue_name,
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

    await event_publisher.close()   

    await engine.dispose()

    logger.info("Microservice shutdown complete.")

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan
)
app.include_router(analyses_router)

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
    try:
        async with request.app.state.engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2)
    except Exception:
        logger.warning("Readiness check: database unreachable", exc_info=True)
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "database_unavailable"})
    return {
        "status": "ready"
    }
