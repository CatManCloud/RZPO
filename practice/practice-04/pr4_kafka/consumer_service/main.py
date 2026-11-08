from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer
import json
import time
import asyncio
from contextlib import asynccontextmanager

received_orders = []
received_notifications = []
received_errors = []

consumer_orders = None
consumer_notifications = None
consumer_errors = None

# Ссылки на фоновые задачи, чтобы их не удалил сборщик мусора
background_tasks = set()


def ts() -> str:
    return time.strftime("%H:%M:%S")


async def process_message(kind: str, data: dict, storage: list):
    """Обработка одного сообщения (имитация долгой работы)"""
    await asyncio.sleep(1)
    storage.append(data)
    print(f"[{ts()}] {kind} PROCESSED: {data}")


async def consume(consumer: AIOKafkaConsumer, kind: str, storage: list):
    """Читает топик и на каждое сообщение запускает отдельную корутину"""
    async for msg in consumer:
        print(f"[{ts()}] {kind} received: {msg.value}")
        task = asyncio.create_task(process_message(kind, msg.value, storage))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)


def make_consumer(topic: str, group_id: str) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        topic,
        bootstrap_servers="localhost:9092",
        group_id=group_id,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_orders, consumer_notifications, consumer_errors

    consumer_orders = make_consumer("orders", "orders-group")
    consumer_notifications = make_consumer("notifications", "notifications-group")
    consumer_errors = make_consumer("errors", "errors-group")

    await consumer_orders.start()
    await consumer_notifications.start()
    await consumer_errors.start()

    tasks = [
        asyncio.create_task(consume(consumer_orders, "Order", received_orders)),
        asyncio.create_task(consume(consumer_notifications, "Notification", received_notifications)),
        asyncio.create_task(consume(consumer_errors, "Error", received_errors)),
    ]
    print("Kafka Consumers started")
    yield
    for t in tasks:
        t.cancel()
    for t in list(background_tasks):
        t.cancel()
    await consumer_orders.stop()
    await consumer_notifications.stop()
    await consumer_errors.stop()


app = FastAPI(title="Consumer Service", lifespan=lifespan)


@app.get("/orders/")
async def get_orders():
    return {"orders": received_orders, "count": len(received_orders)}


@app.get("/notifications/")
async def get_notifications():
    return {"notifications": received_notifications, "count": len(received_notifications)}


@app.get("/errors/")
async def get_errors():
    return {"errors": received_errors, "count": len(received_errors)}


@app.get("/health")
async def health():
    return {"status": "healthy"}