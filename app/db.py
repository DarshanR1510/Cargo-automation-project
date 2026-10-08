"""Database helpers. Plain sqlite3 on purpose, so every query is visible SQL you can learn from."""
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("CARGO_DB", BASE_DIR / "data" / "cargo.db"))
UPLOAD_DIR = BASE_DIR / "data" / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('admin', 'customer')),
    full_name   TEXT NOT NULL,
    email       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS airports (
    code     TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    city     TEXT NOT NULL,
    country  TEXT NOT NULL
);

-- Note: awb_number has no UNIQUE constraint. Ask yourself why that matters.
CREATE TABLE IF NOT EXISTS bookings (
    id                INTEGER PRIMARY KEY,
    awb_number        TEXT NOT NULL,
    customer_id       INTEGER NOT NULL,
    origin            TEXT NOT NULL,
    destination       TEXT NOT NULL,
    pieces            INTEGER NOT NULL,
    weight_kg         REAL NOT NULL,
    length_cm         REAL NOT NULL,
    width_cm          REAL NOT NULL,
    height_cm         REAL NOT NULL,
    volumetric_kg     REAL NOT NULL,
    chargeable_kg     REAL NOT NULL,
    commodity         TEXT,
    special_handling  TEXT,
    flight_date       TEXT NOT NULL,
    status            TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tracking_events (
    id          INTEGER PRIMARY KEY,
    booking_id  INTEGER NOT NULL,
    milestone   TEXT NOT NULL,
    location    TEXT NOT NULL,
    event_time  TEXT NOT NULL,
    remarks     TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY,
    booking_id    INTEGER NOT NULL,
    filename      TEXT NOT NULL,
    content_type  TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    stored_path   TEXT NOT NULL,
    uploaded_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tokens (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    expires_at  REAL NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
