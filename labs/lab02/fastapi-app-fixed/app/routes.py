"""Эндпоинты с исправленными уязвимостями и валидацией через Pydantic."""
import hashlib
import json
import os
import sqlite3
import subprocess  # nosec B404 - вызов без shell, вход валидируется регуляркой

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl

from app.scanner import fetch_url
from app.utils import calculate

router = APIRouter()

HOST_RE = r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$"   # не начинается с "-"
NAME_RE = r"^[A-Za-z0-9_]+$"


class FetchIn(BaseModel):
    url: HttpUrl


class ConfigIn(BaseModel):
    data: str = Field(min_length=1, max_length=10_000)


class RestoreIn(BaseModel):
    data: str = Field(min_length=1, max_length=10_000)


class PasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@router.get("/calc")
def calc(expr: str = Query(..., min_length=1, max_length=100,
                           pattern=r"^[0-9+\-*/%().\s]+$")):
    try:
        return {"result": calculate(expr)}
    except (ValueError, SyntaxError, ZeroDivisionError):
        raise HTTPException(status_code=400, detail="invalid expression")


@router.post("/fetch")
def fetch(body: FetchIn):
    try:
        return {"body": fetch_url(str(body.url))[:200]}
    except ValueError:
        raise HTTPException(status_code=400, detail="URL is not allowed")


@router.get("/ping")
def ping(host: str = Query(..., min_length=1, max_length=253, pattern=HOST_RE)):
    # ИСПРАВЛЕНО (B602): без shell, аргументы списком, валидация host, timeout
    try:
        out = subprocess.run(  # nosec B603 B607 - аргументы списком, host провалидирован
            ["ping", "-c", "1", host],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        raise HTTPException(status_code=503, detail="ping unavailable")
    return {"output": out.stdout}


@router.get("/user")
def get_user(name: str = Query(..., min_length=1, max_length=50, pattern=NAME_RE)):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (name TEXT, role TEXT)")
    conn.execute("INSERT INTO users VALUES ('admin', 'root'), ('guest', 'user')")
    # ИСПРАВЛЕНО (B608): параметризованный запрос
    rows = conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchall()
    return {"rows": rows}


@router.post("/config")
def load_config(body: ConfigIn):
    # ИСПРАВЛЕНО (B506): safe_load
    try:
        return {"config": yaml.safe_load(body.data)}
    except yaml.YAMLError:
        raise HTTPException(status_code=400, detail="invalid YAML")


@router.post("/restore")
def restore(body: RestoreIn):
    # ИСПРАВЛЕНО (B301): JSON вместо pickle
    try:
        return {"obj": json.loads(body.data)}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")


@router.post("/hash")
def hash_password(body: PasswordIn):
    # ИСПРАВЛЕНО (B324): PBKDF2-HMAC-SHA256 с солью вместо MD5
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", body.password.encode(), salt, 600_000)
    return {"salt": salt.hex(), "hash": digest.hex()}
