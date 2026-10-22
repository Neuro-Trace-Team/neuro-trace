import asyncio

from services.ml.src.infrastructure.rabbit_mq_consumer import RabbitMQConsumer


async def main():
    # TODO: Instantiate model wrapper and load ML model

    # TODO: Declare event handlers and inject properties i.e.:
    # prediction_handler = PredictionEventHandler(predictor=predictor)

    # TODO: Declare routing dictionary
    handlers_registry = {}


    # TODO: Setup infrastructure (consumer)
    # TODO: get parameters
    queue_url = "placeholder"
    queue_name = "placeholder"

    consumer = RabbitMQConsumer(
        queue_url=queue_url,
        queue_name=queue_name,
        handlers=handlers_registry
    )

    try:
        await consumer.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        # TODO handle exception
        print("Exception")
    finally:
        await consumer.close()

if __name__ == "__main__":
    asyncio.run(main())