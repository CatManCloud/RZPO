import os
import time

import psutil
from fastapi import FastAPI, HTTPException

from app.routes import router

app = FastAPI(title="Lab2 SAST demo app (fixed)")
app.include_router(router)

START_TIME = time.time()
REQUEST_COUNTER = {"total": 0}

# ИСПРАВЛЕНО (B105): секреты берутся из переменных окружения, а не из кода
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
SECRET_KEY = os.environ.get("SECRET_KEY")


@app.get("/")
def root():
    REQUEST_COUNTER["total"] += 1
    return {"message": "Hello, FastAPI SAST lab!"}


@app.get("/health")
def health():
    REQUEST_COUNTER["total"] += 1
    # ИСПРАВЛЕНО (B101): вместо assert - явная проверка и исключение
    if START_TIME <= 0:
        raise HTTPException(status_code=500, detail="start time is not set")
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
    # ИСПРАВЛЕНО (B104): по умолчанию только localhost; в контейнере адрес
    # задаётся параметром --host в команде запуска (см. Dockerfile)
    uvicorn.run(app, host=os.environ.get("APP_HOST", "127.0.0.1"), port=8000)
