from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import httpx

app = FastAPI(title="User Service", version="1.0.0")

# --- Настройки JWT ---
SECRET_KEY = "super-secret-key-for-lab-only"  # в реальном проекте — переменная окружения
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --- Модели пользователей (CRUD) ---
class UserBase(BaseModel):
    name: str
    email: str
    age: Optional[int] = None


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: int
    created_at: datetime
    is_active: bool = True


class Notification(BaseModel):
    user_id: int
    email: str
    message: str


# --- Модели аутентификации ---
class SignupRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# --- Хранилища (in-memory) ---
users_db = {}
next_user_id = 1

auth_db = {}  # username -> hashed_password


# --- Вспомогательные функции аутентификации ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username not in auth_db:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception


# --- Базовые эндпоинты ---
@app.get("/")
async def root():
    return {"message": "User Service is running!", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# --- Аутентификация ---
@app.post("/signup", status_code=201)
async def signup(data: SignupRequest):
    if data.username in auth_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    auth_db[data.username] = get_password_hash(data.password)
    return {"message": f"User {data.username} registered successfully"}


@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    hashed_password = auth_db.get(form_data.username)
    if not hashed_password or not verify_password(form_data.password, hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}


# --- CRUD над пользователями ---
@app.post("/users/", response_model=User, status_code=201)
async def create_user(user: UserCreate):
    global next_user_id

    for existing_user in users_db.values():
        if existing_user.email == user.email:
            raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        id=next_user_id,
        name=user.name,
        email=user.email,
        age=user.age,
        created_at=datetime.now(),
        is_active=True,
    )
    users_db[next_user_id] = new_user
    next_user_id += 1

    async with httpx.AsyncClient() as client:
        try:
            notification = Notification(
                user_id=new_user.id,
                email=new_user.email,
                message=f"Welcome, {new_user.name}!",
            )
            response = await client.post(
                "http://localhost:8001/notify/",
                json=notification.model_dump(),
                timeout=5.0,
            )
            response.raise_for_status()
        except httpx.RequestError:
            print(f"Failed to send notification for user {new_user.id}")

    return new_user


@app.get("/users/", response_model=List[User])
async def get_users(skip: int = 0, limit: int = 10, min_age: Optional[int] = None):
    users_list = list(users_db.values())
    if min_age is not None:
        users_list = [u for u in users_list if u.age is not None and u.age >= min_age]
    return users_list[skip:skip + limit]


@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]


# --- Защищённые эндпоинты (требуют JWT) ---
@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user: UserCreate, current_user: str = Depends(get_current_user)):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    updated_user = users_db[user_id]
    updated_user.name = user.name
    updated_user.email = user.email
    updated_user.age = user.age
    return updated_user


@app.delete("/users/{user_id}")
async def delete_user(user_id: int, current_user: str = Depends(get_current_user)):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del users_db[user_id]
    return {"message": f"User {user_id} deleted successfully"}


# --- Интеграция с внешним API ---
@app.get("/users/{user_id}/posts")
async def get_user_posts(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://jsonplaceholder.typicode.com/posts",
                params={"userId": user_id},
                timeout=5.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"External API error: {e.response.status_code}")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="External API unavailable")

    return response.json()
