"""
Minimal auth helpers: salted PBKDF2 password hashing + cookie-session
lookups. No third-party auth libraries required.
"""
import hashlib
import hmac
import secrets

from fastapi import Request, HTTPException

from app import db

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest.hex(), digest_hex)


def login_user(request: Request, user_id: int):
    request.session["user_id"] = user_id


def logout_user(request: Request):
    request.session.pop("user_id", None)


def current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get_user_by_id(user_id)


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to use EduGenie.")
    return user
