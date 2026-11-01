from typing import Dict, Optional

from app.models import User

# "База данных" в памяти
fake_users_db: Dict[str, User] = {}
refresh_tokens_blacklist: set = set()          # отозванные refresh-токены (по jti)
revoked_all_at: Dict[str, float] = {}          # username -> время (timestamp) "отозвать всё"


def get_user_by_username(username: str) -> Optional[User]:
    return fake_users_db.get(username)


def create_user(user: User) -> User:
    fake_users_db[user.username] = user
    return user


def blacklist_refresh_token(jti: str) -> None:
    refresh_tokens_blacklist.add(jti)


def is_token_blacklisted(jti: str) -> bool:
    return jti in refresh_tokens_blacklist


def revoke_all_for_user(username: str, ts: float) -> None:
    revoked_all_at[username] = ts


def get_revoked_all_at(username: str) -> float:
    return revoked_all_at.get(username, 0.0)
