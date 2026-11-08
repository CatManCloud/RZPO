from fastapi import FastAPI
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Prometheus Demo")

# Кастомная метрика-счётчик
my_custom_counter = Counter(
    "my_custom_counter",
    "Number of requests to the root endpoint"
)

Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root():
    my_custom_counter.inc()
    return {"message": "Hello from instrumented FastAPI!"}


@app.get("/cpu")
async def cpu_load():
    """Эндпоинт для имитации CPU-нагрузки"""
    for _ in range(10_000_000):
        pass
    return {"status": "loaded"}
