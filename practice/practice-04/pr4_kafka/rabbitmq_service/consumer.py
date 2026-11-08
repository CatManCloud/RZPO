from fastapi import FastAPI
import aio_pika
import json
from contextlib import asynccontextmanager

received_orders = []
received_notifications = []

connection = None


async def on_order(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process():
        data = json.loads(message.body.decode("utf-8"))
        received_orders.append(data)
        print(f"Order received: {data}")


async def on_notification(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process():
        data = json.loads(message.body.decode("utf-8"))
        received_notifications.append(data)
        print(f"Notification received: {data}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global connection
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    orders_queue = await channel.declare_queue("orders", durable=True)
    notifications_queue = await channel.declare_queue("notifications", durable=True)

    await orders_queue.consume(on_order)
    await notifications_queue.consume(on_notification)
    print("RabbitMQ Consumers started")
    yield
    await connection.close()


app = FastAPI(title="RabbitMQ Consumer Service", lifespan=lifespan)


@app.get("/orders/")
async def get_orders():
    return {"orders": received_orders, "count": len(received_orders)}


@app.get("/notifications/")
async def get_notifications():
    return {"notifications": received_notifications, "count": len(received_notifications)}


@app.get("/health")
async def health():
    return {"status": "healthy"}