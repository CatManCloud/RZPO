from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aio_pika
import json
from contextlib import asynccontextmanager


class Order(BaseModel):
    order_id: int
    user_id: int
    product: str
    quantity: int


class Notification(BaseModel):
    user_id: int
    message: str


connection = None
channel = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global connection, channel
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    await channel.declare_queue("orders", durable=True)
    await channel.declare_queue("notifications", durable=True)
    print("RabbitMQ Producer started")
    yield
    await connection.close()
    print("RabbitMQ Producer stopped")


app = FastAPI(title="RabbitMQ Producer Service", lifespan=lifespan)


async def publish(queue_name: str, data: dict):
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(data).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=queue_name,
    )


@app.post("/orders/")
async def create_order(order: Order):
    try:
        await publish("orders", order.model_dump())
        return {"status": "success", "message": f"Order {order.order_id} sent to RabbitMQ"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/")
async def send_notification(notification: Notification):
    try:
        await publish("notifications", notification.model_dump())
        return {"status": "success", "message": f"Notification sent to user {notification.user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}