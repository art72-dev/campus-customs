"""Campus Customs API (FastAPI). Run from hw4/backend:  uvicorn main:app --reload --port 8000

Products, accounts (sign up / log in), the chat route that calls the PydanticAI agent (agent.py), and the
product photos. Needs the local-only data pack in hw4/data/ and the secrets in hw4/.env (see README.md).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import agent
import tools
from models import (
    CatalogListing,
    ChatRequest,
    ChatResponse,
    Conversation,
    LoginRequest,
    ProductDetail,
    SignupRequest,
    SizeStock,
    SortOption,
    User,
)

logger = logging.getLogger("campus_customs")

HW4_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = HW4_DIR / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

load_dotenv(HW4_DIR / ".env")  # hw4/.env (copy of .env.example)
load_dotenv(HW4_DIR.parent / ".env")  # or the folder above hw4/

# ---------------------------------------------------------------------------
# Startup checks: fail early with a clear message instead of a confusing error later
# ---------------------------------------------------------------------------

if not DB_PATH.is_file() or not tools.RAW_PHOTOS.is_dir():
    raise RuntimeError(
        f"Data pack missing: put campus_customs.db and products/ in {DATA_DIR} (see README.md). "
        "The data pack isn't in git."
    )
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:  # never sign sessions with a guessable fallback key
    raise RuntimeError("JWT_SECRET is missing: copy hw4/.env.example to hw4/.env and fill it in (see README.md).")

tools.ensure_chat_schema()
_made = tools.prepare_product_photos()  # first start: white, same-size copies of the photos (~30 s)
if _made:
    logger.warning("Prepared %d product photos in %s", _made, tools.WEB_PHOTOS)

app = FastAPI(title="Campus Customs API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Serve only the cleaned product photos, never the rest of data/ (the .db file).
app.mount("/media", StaticFiles(directory=tools.WEB_PHOTOS), name="media")


def connect() -> sqlite3.Connection:
    """Read/write connection for accounts. (The agent's tools use their own read-only connections.)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@app.get("/api/products", response_model=CatalogListing)
def list_products(
    sort: SortOption = "featured",
    category: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    max_price: float | None = Query(default=None, gt=0),
    size: str | None = None,
    ids: str | None = Query(default=None, description="Comma-separated product ids (chat search results)"),
) -> CatalogListing:
    """The Products page: sorted and filtered by the same catalog tool the agent's browse_catalog uses."""
    id_list = [i for i in ids.split(",") if i] if ids else None
    return tools.catalog(sort, category, color, brand, max_price, size, id_list)


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str) -> ProductDetail:
    with tools.connect() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Product not found")
        stock = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()
    sizes = sorted(
        (SizeStock(size=s["size"], quantity=s["quantity"]) for s in stock),
        key=lambda s: SIZE_ORDER.index(s.size),
    )
    return ProductDetail(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        price=row["price"],
        image_url=tools.photo_url(row["image_file_path"]),
        colors=json.loads(row["colors"]),
        sizes=sizes,
        total_stock=sum(s.quantity for s in sizes),
    )


# ---------------------------------------------------------------------------
# Accounts: sign up, log in, log out, "who am I"
# ---------------------------------------------------------------------------

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 15 * 60
LEGACY_PBKDF2_ROUNDS = 120_000  # seed accounts use "pbkdf2_sha256$<salt>$<hex digest>" at 120,000 rounds

# Argon2id: salted, memory-hard hashing (OWASP's first choice for password storage).
hasher = PasswordHasher()
# Checked when the email doesn't exist, so response time doesn't reveal which emails have accounts.
_DUMMY_HASH = hasher.hash("not-a-real-password")
_failed_logins: dict[str, deque[float]] = defaultdict(deque)


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        _, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), LEGACY_PBKDF2_ROUNDS).hex()
        return hmac.compare_digest(candidate, digest)
    try:
        return hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return False


def to_user(row: sqlite3.Row) -> User:
    return User(id=row["id"], first_name=row["first_name"], last_name=row["last_name"], email=row["email"])


def start_session(response: Response, user_id: int) -> None:
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    token = jwt.encode({"sub": str(user_id), "exp": expires}, JWT_SECRET, algorithm="HS256")
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,  # page JavaScript can't read it, so XSS can't steal the session
        samesite="lax",  # not sent on cross-site POSTs (CSRF protection)
        secure=False,  # local http dev server; set True when served over https
    )


def current_user(request: Request) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    try:
        user_id = int(jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please log in again")
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return to_user(row)


def optional_user(request: Request) -> User | None:
    try:
        return current_user(request)
    except HTTPException:
        return None


def _too_many_failures(email: str) -> bool:
    attempts = _failed_logins[email]
    while attempts and time.monotonic() - attempts[0] > LOCKOUT_SECONDS:
        attempts.popleft()
    return len(attempts) >= MAX_FAILED_LOGINS


@app.post("/api/auth/signup", response_model=User, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, response: Response) -> User:
    email = body.email.lower()
    password_hash = hasher.hash(body.password)
    with connect() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
                (f"{body.first_name} {body.last_name}", body.first_name, body.last_name, email, password_hash),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    start_session(response, row["id"])
    return to_user(row)


@app.post("/api/auth/login", response_model=User)
def login(body: LoginRequest, response: Response) -> User:
    email = body.email.lower()
    if _too_many_failures(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again in 15 minutes.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
    ok = verify_password(body.password, row["password_hash"] if row else _DUMMY_HASH) and row is not None
    if not ok:
        _failed_logins[email].append(time.monotonic())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    _failed_logins.pop(email, None)
    stored = row["password_hash"]
    # Upgrade legacy PBKDF2 (and outdated Argon2 settings) to current Argon2id on successful login.
    if stored.startswith("pbkdf2_sha256$") or hasher.check_needs_rehash(stored):
        with connect() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hasher.hash(body.password), row["id"]))
    start_session(response, row["id"])
    return to_user(row)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax")


@app.get("/api/auth/me", response_model=User)
def me(request: Request) -> User:
    return current_user(request)


# ---------------------------------------------------------------------------
# Chat (the PydanticAI agent lives in agent.py)
# ---------------------------------------------------------------------------


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Reply from the agent. Guests can chat; logged-in shoppers' questions and results are saved."""
    user = optional_user(request)
    conversation_id = body.conversation_id or uuid.uuid4().hex
    body = body.model_copy(update={"conversation_id": conversation_id})
    try:
        response = await agent.run_chat(
            body,
            user_id=user.id if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
            email=user.email if user else None,
        )
    except Exception:
        logger.exception("Chat agent failed")
        raise HTTPException(502, "Audrey is momentarily unavailable. Please try again in a moment.")

    response.conversation_id = conversation_id
    if user:
        tools.save_exchange(user.id, conversation_id, body.message, response)
        response.saved = True
    return response


@app.get("/api/chat/history", response_model=list[Conversation])
def chat_history(request: Request) -> list[Conversation]:
    """The logged-in shopper's past chats (newest first), each with its messages, cards and page results."""
    user = current_user(request)
    return tools.load_conversations(user.id)
