import logging, json, sys, random
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

EXTRA_KEYS = ("method", "path", "status_code", "duration", "client_ip", "user_agent")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        for k in EXTRA_KEYS:
            if hasattr(record, k):
                log[k] = getattr(record, k)
        return json.dumps(log, ensure_ascii=False)

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

app = FastAPI(title="FastAPI with Structured Logging")
Instrumentator().instrument(app).expose(app)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.utcnow()
    response = await call_next(request)
    duration = (datetime.utcnow() - start).total_seconds()
    level = logging.ERROR if response.status_code >= 500 else logging.INFO
    logger.log(level, "Request completed", extra={
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration": duration,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    })
    return response

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Hello!"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/cpu")
async def cpu_load():
    logger.info("CPU load endpoint called")
    for _ in range(10_000_000):
        pass
    return {"status": "loaded"}

@app.get("/crash")
async def crash():
    if random.random() < 0.3:
        logger.error("Random crash occurred")
        raise HTTPException(status_code=500, detail="Random crash")
    return {"status": "ok"}