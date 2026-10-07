import time
import psutil
from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="Lab2 SAST demo app")
app.include_router(router)

START_TIME = time.time()
REQUEST_COUNTER = {"total": 0}

# УЯЗВИМОСТЬ (Bandit B105): захардкоженный пароль/секрет
ADMIN_PASSWORD = "admin12345"
SECRET_KEY = "super-secret-key-do-not-share"


@app.get("/")
def root():
    REQUEST_COUNTER["total"] += 1
    return {"message": "Hello, FastAPI SAST lab!"}


@app.get("/health")
def health():
    REQUEST_COUNTER["total"] += 1
    # УЯЗВИМОСТЬ (Bandit B101): assert в production-коде
    assert START_TIME > 0, "start time must be set"
    return {"status": "ok", "uptime_sec": round(time.time() - START_TIME, 2)}


@app.get("/cpu")
def cpu():
    REQUEST_COUNTER["total"] += 1
    return {"cpu_percent": psutil.cpu_percent(interval=0.5),
            "cores": psutil.cpu_count()}


@app.get("/metrics")
def metrics():
    REQUEST_COUNTER["total"] += 1
    mem = psutil.virtual_memory()
    return {"requests_total": REQUEST_COUNTER["total"],
            "memory_percent": mem.percent}


if __name__ == "__main__":
    import uvicorn
    # УЯЗВИМОСТЬ (Bandit B104): привязка ко всем интерфейсам
    uvicorn.run(app, host="0.0.0.0", port=8000)
