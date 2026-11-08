from fastapi import FastAPI, HTTPException
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="FastAPI with Grafana Monitoring")

# Кастомная метрика-счётчик
my_custom_counter = Counter(
    "my_custom_counter",
    "Number of requests to the root endpoint"
)

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app)


@app.get("/")
async def root():
    my_custom_counter.inc()
    return {"message": "Hello from monitored FastAPI!"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/cpu")
async def cpu_load():
    """Эндпоинт для имитации CPU-нагрузки"""
    for _ in range(10_000_000):
        pass
    return {"status": "loaded"}


@app.get("/error")
async def error():
    """Эндпоинт для имитации ошибки 5xx"""
    raise HTTPException(status_code=500, detail="Simulated error")
