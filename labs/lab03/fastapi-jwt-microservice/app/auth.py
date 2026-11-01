import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import (get_revoked_all_at, get_user_by_username,
                          is_token_blacklisted)
from app.models import TokenData, User

load_dotenv()

# ---- Конфигурация: без SECRET_KEY приложение не стартует ----
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY не задан. Создайте файл .env (см. .env.example)")

ALGORITHM = "HS256"
# Задание 2: время жизни настраивается через окружение
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Аудит попыток аутентификации (Этап 6, п.4)
audit_log = logging.getLogger("auth.audit")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(message)s",
    handlers=[logging.FileHandler("auth.log", encoding="utf-8"),
              logging.StreamHandler()],
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_user_with_hash(user_data) -> User:
    return User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role,
    )


def authenticate_user(username: str, password: str) -> User | None:
    user = get_user_by_username(username)
    if not user or user.disabled or not verify_password(password, user.password_hash):
        audit_log.warning("LOGIN FAILED username=%s", username)
        return None
    audit_log.info("LOGIN OK username=%s", username)
    return user


def _create_token(data: dict, delta: timedelta, token_type: str) -> str:
    now = now_utc()
    to_encode = data.copy()
    to_encode.update({
        "exp": now + delta,
        "iat": now.timestamp(),      # нужно для /token/revoke-all
        "jti": uuid.uuid4().hex,     # уникальный id токена -> blacklist
        "type": token_type,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return _create_token(
        data, expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), "access")


def create_refresh_token(data: dict, expires_at: int | None = None) -> str:
    # expires_at: если передан, срок жизни не продлевается (этап 6, п.2)
    now = now_utc()
    if expires_at is None:
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    to_encode = {
        **data,
        "exp": expire,
        "iat": now.timestamp(),
        "jti": uuid.uuid4().hex,
        "type": "refresh",
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_refresh_token(refresh_token: str) -> dict:
    """Возвращает payload, если refresh-токен валиден и не отозван."""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    if is_token_blacklisted(payload.get("jti", "")):
        raise HTTPException(status_code=401, detail="Token revoked")
    username = payload.get("sub")
    if username is None or get_user_by_username(username) is None:
        raise HTTPException(status_code=401, detail="User not found")
    if payload.get("iat", 0) < get_revoked_all_at(username):
        raise HTTPException(status_code=401, detail="Token revoked")
    return payload


def verify_refresh_token(refresh_token: str) -> User:
    payload = decode_refresh_token(refresh_token)
    return get_user_by_username(payload["sub"])


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception
    # refresh-токен нельзя использовать как access
    if payload.get("type") != "access":
        raise credentials_exception
    username = payload.get("sub")
    if username is None:
        raise credentials_exception
    token_data = TokenData(username=username)
    user = get_user_by_username(token_data.username)
    if user is None or user.disabled:
        raise credentials_exception
    if payload.get("iat", 0) < get_revoked_all_at(username):
        raise credentials_exception
    return user


def require_role(role: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker
