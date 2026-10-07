"""Дополнительные эндпоинты с намеренными уязвимостями."""
import hashlib
import pickle
import sqlite3
import subprocess

import yaml
from fastapi import APIRouter

from app.scanner import fetch_url
from app.utils import calculate

router = APIRouter()


@router.get("/calc")
def calc(expr: str):
    # Данные пользователя -> eval (через utils.calculate)
    return {"result": calculate(expr)}


@router.get("/fetch")
def fetch(url: str):
    return {"body": fetch_url(url)[:200]}


@router.get("/ping")
def ping(host: str):
    # УЯЗВИМОСТЬ (Bandit B602 HIGH): shell=True + пользовательский ввод -> command injection
    out = subprocess.check_output("ping -c 1 " + host, shell=True)
    return {"output": out.decode()}


@router.get("/user")
def get_user(name: str):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (name TEXT, role TEXT)")
    # УЯЗВИМОСТЬ (Bandit B608): SQL-инъекция через f-строку
    query = f"SELECT * FROM users WHERE name = '{name}'"
    return {"rows": conn.execute(query).fetchall()}


@router.post("/config")
def load_config(data: str):
    # УЯЗВИМОСТЬ (Bandit B506): yaml.load без SafeLoader
    return {"config": yaml.load(data, Loader=yaml.Loader)}


@router.post("/restore")
def restore(blob: str):
    # УЯЗВИМОСТЬ (Bandit B301): pickle на недоверенных данных
    return {"obj": str(pickle.loads(bytes.fromhex(blob)))}


@router.get("/hash")
def hash_password(password: str):
    # УЯЗВИМОСТЬ (Bandit B324 HIGH): слабый хеш MD5
    return {"hash": hashlib.md5(password.encode()).hexdigest()}
