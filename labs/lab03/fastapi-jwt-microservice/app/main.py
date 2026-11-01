import os
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import (audit_log, authenticate_user, create_access_token,
                      create_refresh_token, create_user_with_hash,
                      decode_refresh_token, get_current_user,
                      get_password_hash, now_utc, require_role, verify_password)
from app.database import (blacklist_refresh_token, create_user, fake_users_db,
                          get_user_by_username, revoke_all_for_user)
from app.models import (ChangePassword, RefreshToken, Token, User,
                        UserCreate, UserLogin)

app = FastAPI(title="JWT Protected Microservice")

ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")]


# Этап 6, п.1: CSRF - проверка заголовка Origin у изменяющих запросов
@app.middleware("http")
async def csrf_origin_check(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            audit_log.warning("CSRF BLOCKED origin=%s path=%s", origin, request.url.path)
            return JSONResponse(status_code=403,
                                content={"detail": "CSRF check failed: untrusted origin"})
    return await call_next(request)


def issue_tokens(username: str, refresh_exp: int | None = None):
    return {
        "access_token": create_access_token({"sub": username}),
        "refresh_token": create_refresh_token({"sub": username}, expires_at=refresh_exp),
        "token_type": "bearer",
    }


# ---------------- ПУБЛИЧНЫЕ ЭНДПОИНТЫ ----------------
@app.get("/")
async def public_root():
    return {
        "message": "Welcome to JWT Protected Microservice!",
        "public_info": "This is public information",
        "endpoints": {
            "public": ["/", "/public-info", "/docs", "/openapi.json"],
            "auth": ["/register", "/token", "/token/custom", "/refresh",
                     "/logout", "/token/revoke-all", "/change-password"],
            "protected": ["/protected", "/protected/admin"],
        },
    }


@app.get("/public-info")
async def public_info():
    return {
        "public_data": {"app_name": "JWT Microservice", "version": "1.0.0",
                        "status": "operational"},
        "note": "Full information available only with authentication",
    }


# ---------------- АУТЕНТИФИКАЦИЯ ----------------
@app.post("/register", status_code=201)
async def register(user_data: UserCreate):
    if get_user_by_username(user_data.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    user = create_user_with_hash(user_data)
    create_user(user)
    audit_log.info("REGISTER username=%s role=%s", user.username, user.role)
    return {"message": "User created successfully", "username": user.username,
            "email": user.email, "role": user.role}


@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return issue_tokens(user.username)


@app.post("/token/custom", response_model=Token)
async def login_custom(login_data: UserLogin):
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Incorrect username or password")
    return issue_tokens(user.username)


@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_data: RefreshToken):
    payload = decode_refresh_token(refresh_data.refresh_token)
    blacklist_refresh_token(payload["jti"])
    return issue_tokens(payload["sub"], refresh_exp=payload["exp"])


@app.post("/logout")
async def logout(refresh_data: RefreshToken):
    payload = decode_refresh_token(refresh_data.refresh_token)
    blacklist_refresh_token(payload["jti"])
    audit_log.info("LOGOUT username=%s", payload["sub"])
    return {"message": "Successfully logged out"}


@app.post("/token/revoke-all")
async def revoke_all(current_user: User = Depends(get_current_user)):
    revoke_all_for_user(current_user.username, now_utc().timestamp())
    audit_log.info("REVOKE-ALL username=%s", current_user.username)
    return {"message": "All tokens revoked, please log in again"}


# Этап 6, п.3: смена пароля инвалидирует все токены
@app.post("/change-password")
async def change_password(data: ChangePassword,
                          current_user: User = Depends(get_current_user)):
    if not verify_password(data.old_password, current_user.password_hash):
        audit_log.warning("CHANGE-PASSWORD FAILED username=%s", current_user.username)
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    current_user.password_hash = get_password_hash(data.new_password)
    revoke_all_for_user(current_user.username, now_utc().timestamp())
    audit_log.info("CHANGE-PASSWORD username=%s", current_user.username)
    return {"message": "Password changed. All tokens revoked, log in again"}


# ---------------- ЗАЩИЩЁННЫЕ ЭНДПОИНТЫ ----------------
@app.get("/protected")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    return {
        "message": f"Hello, {current_user.username}! This is protected information",
        "user_data": {
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "created_at": current_user.created_at.isoformat(),
        },
    }


@app.get("/protected/admin")
async def admin_endpoint(current_user: User = Depends(require_role("admin"))):
    return {"message": "Admin panel", "users": list(fake_users_db.keys())}