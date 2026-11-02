import os
from typing import List, Optional

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="FastAPI on Kubernetes")


class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        database=os.getenv("DB_NAME", "fastapi_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
    )


@app.on_event("startup")
def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            price FLOAT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


@app.post("/items/", status_code=201)
async def create_item(item: Item):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO items (name, description, price) VALUES (%s, %s, %s)",
            (item.name, item.description, item.price),
        )
        conn.commit()
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=400, detail="Item already exists")
    finally:
        cur.close()
        conn.close()
    return {"message": f"Item {item.name} created"}


@app.get("/items/", response_model=List[Item])
async def get_items():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, description, price FROM items")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"name": x[0], "description": x[1], "price": x[2]} for x in rows]


@app.get("/")
async def root():
    return {"message": "Hello from Kubernetes!"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/version")
async def version():
    return {"version": os.getenv("APP_VERSION", "unknown")}