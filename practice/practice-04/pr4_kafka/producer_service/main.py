from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer
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


class ErrorMessage(BaseModel):
    service: str
    error_code: int
    description: str


producer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",  # или localhost:9093, если идёте через HAProxy
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    print("Kafka Producer started")
    yield
    await producer.stop()
    print("Kafka Producer stopped")


app = FastAPI(title="Producer Service", lifespan=lifespan)


@app.post("/orders/")
async def create_order(order: Order):
    """Публикация сообщения о заказе в топик orders"""
    try:
        await producer.send_and_wait("orders", value=order.model_dump())
        return {"status": "success", "message": f"Order {order.order_id} sent to Kafka"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/")
async def send_notification(notification: Notification):
    """Публикация уведомления в топик notifications"""
    try:
        await producer.send_and_wait("notifications", value=notification.model_dump())
        return {"status": "success", "message": f"Notification sent to user {notification.user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/errors/")
async def send_error(error: ErrorMessage):
    """Публикация сообщения об ошибке в топик errors"""
    try:
        await producer.send_and_wait("errors", value=error.model_dump())
        return {"status": "success", "message": f"Error from {error.service} sent to Kafka"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}