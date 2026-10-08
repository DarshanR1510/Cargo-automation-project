"""Cargo QA Lab: a small air cargo booking app built to be tested.

Run:  python run.py
Bugs: planted on purpose. Set CARGO_BUGS=0 to run the "fixed" version.
"""
import asyncio
from contextlib import asynccontextmanager
import csv
import io
import os
import random
import secrets
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.db import UPLOAD_DIR, connect, get_db
from app.domain import (MILESTONE_NAMES, MILESTONES, SPECIAL_HANDLING, calc_weights,
                        is_valid_awb, make_awb)
from app.seed import ensure_database, reset_database

BUGS = os.getenv("CARGO_BUGS", "1") != "0"
SLOW = os.getenv("CARGO_SLOW", "1") != "0"
TEST_MODE = os.getenv("CARGO_TEST_MODE", "1") != "0"
TOKEN_TTL = int(os.getenv("CARGO_TOKEN_TTL", "900"))
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Cargo QA Lab", version="1.0.0", lifespan=lifespan,
              description="Air cargo booking API built for QA practice. See docs/SPEC.md.")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals.update(BUGS=BUGS, MILESTONE_NAMES=MILESTONE_NAMES, SPECIAL_HANDLING=SPECIAL_HANDLING)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


async def latency(low: float, high: float) -> None:
    if SLOW:
        await asyncio.sleep(random.uniform(low, high))


# ---------------------------------------------------------------- auth

def resolve_user(conn, token: Optional[str]):
    """Returns (user, problem). problem is None, 'missing', 'invalid' or 'expired'."""
    if not token:
        return None, "missing"
    row = conn.execute(
        "SELECT u.*, t.expires_at FROM tokens t JOIN users u ON u.id = t.user_id WHERE t.token = ?",
        (token,),
    ).fetchone()
    if not row:
        return None, "invalid"
    if row["expires_at"] < time.time():
        return None, "expired"
    return dict(row), None


def token_from(request: Request, authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get("session")


def current_user(request: Request, authorization: Optional[str] = Header(None), conn=Depends(get_db)):
    user, problem = resolve_user(conn, token_from(request, authorization))
    if problem == "expired":
        if BUGS:
            raise RuntimeError("token expired")  # surfaces as an unhandled 500
        raise HTTPException(401, "Token expired")
    if problem:
        raise HTTPException(401, "Not authenticated")
    return user


def admin_user(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def page_user(request: Request, conn):
    user, _ = resolve_user(conn, request.cookies.get("session"))
    return user


def create_token(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO tokens VALUES (?,?,?)", (token, user_id, time.time() + TOKEN_TTL))
    conn.commit()
    return token


# ---------------------------------------------------------------- serialisers

def booking_dict(row) -> dict:
    data = dict(row)
    data["status_name"] = MILESTONE_NAMES.get(data["status"], data["status"])
    return data


def load_booking(conn, booking_id: int):
    return conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()


def can_view(user, booking) -> bool:
    return user["role"] == "admin" or booking["customer_id"] == user["id"]


def events_for(conn, booking_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT milestone, location, event_time, remarks FROM tracking_events WHERE booking_id = ? ORDER BY event_time, id",
        (booking_id,),
    ).fetchall()
    return [dict(r, milestone_name=MILESTONE_NAMES.get(r["milestone"], r["milestone"])) for r in rows]


# ---------------------------------------------------------------- API: auth

class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login", tags=["auth"])
def api_login(body: LoginIn, conn=Depends(get_db)):
    user = conn.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    if not user or user["password"] != body.password:
        raise HTTPException(401, "Invalid username or password")
    token = create_token(conn, user["id"])
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_TTL, "role": user["role"]}


@app.post("/api/auth/logout", tags=["auth"], status_code=204)
def api_logout(request: Request, authorization: Optional[str] = Header(None), conn=Depends(get_db)):
    token = token_from(request, authorization)
    if token:
        conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
        conn.commit()


@app.get("/api/me", tags=["auth"])
def api_me(user=Depends(current_user)):
    return {k: user[k] for k in ("id", "username", "role", "full_name", "email")}


# ---------------------------------------------------------------- API: reference data

@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "bugs_enabled": BUGS}


@app.get("/api/airports", tags=["reference"])
def api_airports(conn=Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT * FROM airports ORDER BY code")]


# ---------------------------------------------------------------- API: bookings

class BookingIn(BaseModel):
    origin: str = Field(..., examples=["AUH"])
    destination: str = Field(..., examples=["LHR"])
    pieces: int = Field(..., examples=[3])
    weight_kg: float = Field(..., examples=[120.5])
    length_cm: float = Field(..., examples=[100])
    width_cm: float = Field(..., examples=[80])
    height_cm: float = Field(..., examples=[60])
    commodity: str = Field(..., examples=["Electronics"])
    special_handling: str = Field("GEN", examples=["GEN"])
    flight_date: date = Field(..., examples=["2026-12-01"])


class BookingPatch(BaseModel):
    pieces: Optional[int] = None
    weight_kg: Optional[float] = None
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    commodity: Optional[str] = None
    flight_date: Optional[date] = None


def validate_booking(conn, data: dict) -> list[str]:
    errors = []
    airports = {r["code"] for r in conn.execute("SELECT code FROM airports")}
    if "origin" in data:
        data["origin"] = data["origin"].strip().upper()
        data["destination"] = data["destination"].strip().upper()
        if data["origin"] not in airports:
            errors.append("origin: unknown airport code")
        if data["destination"] not in airports:
            errors.append("destination: unknown airport code")
        if data["origin"] == data["destination"]:
            errors.append("destination: must be different from origin")
    if data.get("pieces") is not None and not 1 <= data["pieces"] <= 999:
        errors.append("pieces: must be between 1 and 999")
    if data.get("weight_kg") is not None:
        weight = data["weight_kg"]
        too_low = weight < 0 if BUGS else weight <= 0
        if too_low or weight > 10000:
            errors.append("weight_kg: must be greater than 0 and at most 10000")
    for dim in ("length_cm", "width_cm", "height_cm"):
        if data.get(dim) is not None and not 0 < data[dim] <= 300:
            errors.append(f"{dim}: must be greater than 0 and at most 300")
    if "commodity" in data and data["commodity"] is not None and not data["commodity"].strip():
        errors.append("commodity: is required")
    if "special_handling" in data and data["special_handling"] not in SPECIAL_HANDLING:
        errors.append("special_handling: must be one of " + ", ".join(SPECIAL_HANDLING))
    if data.get("flight_date") is not None and data["flight_date"] < date.today():
        errors.append("flight_date: cannot be in the past")
    return errors


@app.get("/api/bookings", tags=["bookings"])
async def api_list_bookings(status: Optional[str] = None, origin: Optional[str] = None,
                            destination: Optional[str] = None, search: Optional[str] = None,
                            page: int = 1, page_size: int = 10,
                            user=Depends(current_user), conn=Depends(get_db)):
    await latency(0.1, 1.2)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    where, params = [], []
    if user["role"] != "admin":
        where.append("customer_id = ?")
        params.append(user["id"])
    for column, value in (("status", status), ("origin", origin), ("destination", destination)):
        if value:
            where.append(f"{column} = ?")
            params.append(value.upper())
    if search:
        where.append("(awb_number LIKE ? OR commodity LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM bookings {clause}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM bookings {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {"items": [booking_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@app.get("/api/bookings/export.csv", tags=["bookings"])
def api_export(user=Depends(current_user), conn=Depends(get_db)):
    sql = "SELECT awb_number, origin, destination, pieces, weight_kg, chargeable_kg, commodity, status, flight_date FROM bookings"
    params = []
    if user["role"] != "admin":
        sql += " WHERE customer_id = ?"
        params.append(user["id"])
    rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["awb_number", "origin", "destination", "pieces", "weight_kg", "chargeable_kg", "commodity", "status", "flight_date"])
    writer.writerows([list(r) for r in rows])
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=bookings.csv"})


@app.post("/api/bookings", tags=["bookings"], status_code=201)
async def api_create_booking(body: BookingIn, user=Depends(current_user), conn=Depends(get_db)):
    if user["role"] != "customer":
        raise HTTPException(403, "Only customers can create bookings")
    data = body.model_dump()
    errors = validate_booking(conn, data)
    if errors:
        return JSONResponse(status_code=400, content={"detail": "Validation failed", "errors": errors})
    await latency(0.6, 0.9)
    last = conn.execute("SELECT awb_number FROM bookings ORDER BY id DESC LIMIT 1").fetchone()
    serial = int(last[0][4:11]) + 1 if last else 1000001
    awb = make_awb(serial)
    volumetric, chargeable = calc_weights(data["weight_kg"], data["length_cm"], data["width_cm"],
                                          data["height_cm"], buggy=BUGS)
    stamp = now_iso()
    cur = conn.execute(
        """INSERT INTO bookings (awb_number, customer_id, origin, destination, pieces, weight_kg,
           length_cm, width_cm, height_cm, volumetric_kg, chargeable_kg, commodity, special_handling,
           flight_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (awb, user["id"], data["origin"], data["destination"], data["pieces"], data["weight_kg"],
         data["length_cm"], data["width_cm"], data["height_cm"], volumetric, chargeable,
         data["commodity"].strip(), data["special_handling"], data["flight_date"].isoformat(),
         "BKD", stamp, stamp),
    )
    booking_id = cur.lastrowid
    if not (BUGS and data["special_handling"] == "DGR"):
        conn.execute(
            "INSERT INTO tracking_events (booking_id, milestone, location, event_time, remarks) VALUES (?,?,?,?,?)",
            (booking_id, "BKD", data["origin"], stamp, "Booking confirmed"),
        )
    conn.commit()
    return booking_dict(load_booking(conn, booking_id))


@app.get("/api/bookings/{booking_id}", tags=["bookings"])
def api_get_booking(booking_id: int, user=Depends(current_user), conn=Depends(get_db)):
    booking = load_booking(conn, booking_id)
    if not booking or (not BUGS and not can_view(user, booking)):
        raise HTTPException(404, "Booking not found")
    data = booking_dict(booking)
    data["events"] = events_for(conn, booking_id)
    return data


@app.patch("/api/bookings/{booking_id}", tags=["bookings"])
def api_update_booking(booking_id: int, body: BookingPatch, user=Depends(current_user), conn=Depends(get_db)):
    booking = load_booking(conn, booking_id)
    if not booking or not can_view(user, booking):
        raise HTTPException(404, "Booking not found")
    if booking["status"] != "BKD":
        raise HTTPException(409, "Booking can no longer be modified")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "No fields to update")
    errors = validate_booking(conn, dict(changes))
    if errors:
        return JSONResponse(status_code=400, content={"detail": "Validation failed", "errors": errors})
    merged = {**dict(booking), **changes}
    volumetric, chargeable = calc_weights(merged["weight_kg"], merged["length_cm"], merged["width_cm"],
                                          merged["height_cm"], buggy=BUGS)
    changes.update(volumetric_kg=volumetric, chargeable_kg=chargeable, updated_at=now_iso())
    if "flight_date" in changes:
        changes["flight_date"] = changes["flight_date"].isoformat()
    sets = ", ".join(f"{k} = ?" for k in changes)
    conn.execute(f"UPDATE bookings SET {sets} WHERE id = ?", list(changes.values()) + [booking_id])
    conn.commit()
    return booking_dict(load_booking(conn, booking_id))


@app.post("/api/bookings/{booking_id}/cancel", tags=["bookings"])
def api_cancel(booking_id: int, user=Depends(current_user), conn=Depends(get_db)):
    booking = load_booking(conn, booking_id)
    if not booking or not can_view(user, booking):
        raise HTTPException(404, "Booking not found")
    if booking["status"] != "BKD":
        raise HTTPException(409, "Only bookings in BKD status can be cancelled")
    stamp = now_iso()
    conn.execute("UPDATE bookings SET status = 'CAN', updated_at = ? WHERE id = ?", (stamp, booking_id))
    conn.execute(
        "INSERT INTO tracking_events (booking_id, milestone, location, event_time, remarks) VALUES (?,?,?,?,?)",
        (booking_id, "CAN", booking["origin"], stamp, "Cancelled by customer"),
    )
    conn.commit()
    return booking_dict(load_booking(conn, booking_id))


# ---------------------------------------------------------------- API: tracking

@app.get("/api/tracking/{awb}", tags=["tracking"])
async def api_tracking(awb: str, conn=Depends(get_db)):
    await latency(0.2, 0.8)
    awb = awb.strip()
    if not is_valid_awb(awb):
        raise HTTPException(400, "Invalid AWB number")
    booking = conn.execute("SELECT * FROM bookings WHERE awb_number = ? ORDER BY id LIMIT 1", (awb,)).fetchone()
    if not booking:
        raise HTTPException(404, "Shipment not found")
    return {
        "awb_number": booking["awb_number"], "origin": booking["origin"],
        "destination": booking["destination"], "pieces": booking["pieces"],
        "chargeable_kg": booking["chargeable_kg"], "status": booking["status"],
        "status_name": MILESTONE_NAMES.get(booking["status"]),
        "events": events_for(conn, booking["id"]),
    }


class EventIn(BaseModel):
    milestone: str = Field(..., examples=["RCS"])
    location: str = Field(..., examples=["AUH"])
    remarks: Optional[str] = None


@app.post("/api/bookings/{booking_id}/events", tags=["tracking"], status_code=201)
def api_add_event(booking_id: int, body: EventIn, user=Depends(admin_user), conn=Depends(get_db)):
    booking = load_booking(conn, booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found")
    milestone = body.milestone.strip().upper()
    if milestone not in MILESTONES:
        raise HTTPException(400, "Unknown milestone")
    if booking["status"] in ("CAN", "DLV"):
        raise HTTPException(409, f"Booking is {booking['status']}, no more events allowed")
    if not BUGS:
        current = MILESTONES.index(booking["status"]) if booking["status"] in MILESTONES else -1
        if MILESTONES.index(milestone) != current + 1:
            raise HTTPException(409, f"Next milestone must be {MILESTONES[current + 1]}")
    stamp = now_iso()
    conn.execute(
        "INSERT INTO tracking_events (booking_id, milestone, location, event_time, remarks) VALUES (?,?,?,?,?)",
        (booking_id, milestone, body.location.strip().upper(), stamp, body.remarks),
    )
    conn.execute("UPDATE bookings SET status = ?, updated_at = ? WHERE id = ?", (milestone, stamp, booking_id))
    conn.commit()
    return {"booking_id": booking_id, "milestone": milestone, "event_time": stamp}


# ---------------------------------------------------------------- API: documents

@app.post("/api/bookings/{booking_id}/documents", tags=["documents"], status_code=201)
async def api_upload(booking_id: int, file: UploadFile = File(...), user=Depends(current_user), conn=Depends(get_db)):
    booking = load_booking(conn, booking_id)
    if not booking or not can_view(user, booking):
        raise HTTPException(404, "Booking not found")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only PDF, PNG and JPG files are allowed")
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "File is empty")
    if not BUGS and len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 5 MB")
    stored = UPLOAD_DIR / f"{booking_id}_{secrets.token_hex(4)}{extension}"
    stored.write_bytes(content)
    cur = conn.execute(
        "INSERT INTO documents (booking_id, filename, content_type, size_bytes, stored_path, uploaded_at) VALUES (?,?,?,?,?,?)",
        (booking_id, file.filename, ALLOWED_EXTENSIONS[extension], len(content), str(stored), now_iso()),
    )
    conn.commit()
    return {"id": cur.lastrowid, "filename": file.filename, "size_bytes": len(content)}


@app.get("/api/bookings/{booking_id}/documents", tags=["documents"])
def api_list_documents(booking_id: int, user=Depends(current_user), conn=Depends(get_db)):
    booking = load_booking(conn, booking_id)
    if not booking or not can_view(user, booking):
        raise HTTPException(404, "Booking not found")
    rows = conn.execute("SELECT id, filename, content_type, size_bytes, uploaded_at FROM documents WHERE booking_id = ? ORDER BY id",
                        (booking_id,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/documents/{doc_id}", tags=["documents"])
def api_download(doc_id: int, user=Depends(current_user), conn=Depends(get_db)):
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    booking = load_booking(conn, doc["booking_id"]) if doc else None
    if not doc or not booking or not can_view(user, booking):
        raise HTTPException(404, "Document not found")
    return FileResponse(doc["stored_path"], media_type=doc["content_type"], filename=doc["filename"])


# ---------------------------------------------------------------- API: admin

@app.get("/api/admin/summary", tags=["admin"])
def api_summary(user=Depends(admin_user), conn=Depends(get_db)):
    by_status = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM bookings GROUP BY status")}
    active_filter = "" if BUGS else "WHERE status <> 'CAN'"
    row = conn.execute(f"SELECT COUNT(*) AS n, COALESCE(SUM(chargeable_kg), 0) AS kg FROM bookings {active_filter}").fetchone()
    return {"active_bookings": row["n"], "active_chargeable_kg": round(row["kg"], 1), "by_status": by_status}


# ---------------------------------------------------------------- API: test support

@app.post("/api/test/reset", tags=["test support"])
def api_reset():
    if not TEST_MODE:
        raise HTTPException(404, "Not found")
    reset_database()
    return {"status": "reset"}


# ---------------------------------------------------------------- UI pages

def redirect_login(next_path: str = "/bookings"):
    return RedirectResponse(f"/login?next={next_path}", status_code=303)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request, conn=Depends(get_db)):
    return RedirectResponse("/bookings" if page_user(request, conn) else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, next: str = "/bookings"):
    return templates.TemplateResponse(request, "login.html", {"user": None, "error": None, "next": next})


@app.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login_submit(request: Request, username: str = Form(""), password: str = Form(""),
                 next: str = Form("/bookings"), conn=Depends(get_db)):
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
    if not user or user["password"] != password:
        return templates.TemplateResponse(request, "login.html",
                                          {"user": None, "error": "Invalid username or password", "next": next},
                                          status_code=401)
    token = create_token(conn, user["id"])
    target = next if next.startswith("/") else "/bookings"
    if user["role"] == "admin" and target == "/bookings":
        target = "/admin"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=TOKEN_TTL)
    return response


@app.get("/logout", include_in_schema=False)
def logout(request: Request, conn=Depends(get_db)):
    token = request.cookies.get("session")
    if token:
        conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
        conn.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session")
    return response


@app.get("/bookings", response_class=HTMLResponse, include_in_schema=False)
def bookings_page(request: Request, conn=Depends(get_db)):
    user = page_user(request, conn)
    if not user:
        return redirect_login("/bookings")
    return templates.TemplateResponse(request, "bookings.html", {"user": user})


@app.get("/bookings/new", response_class=HTMLResponse, include_in_schema=False)
def new_booking_page(request: Request, conn=Depends(get_db)):
    user = page_user(request, conn)
    if not user:
        return redirect_login("/bookings/new")
    airports = conn.execute("SELECT * FROM airports ORDER BY code").fetchall()
    return templates.TemplateResponse(request, "new_booking.html",
                                      {"user": user, "airports": airports, "today": date.today().isoformat()})


@app.get("/bookings/{booking_id}", response_class=HTMLResponse, include_in_schema=False)
def booking_detail_page(request: Request, booking_id: int, conn=Depends(get_db)):
    user = page_user(request, conn)
    if not user:
        return redirect_login(f"/bookings/{booking_id}")
    booking = load_booking(conn, booking_id)
    if not booking or (not BUGS and not can_view(user, booking)):
        return templates.TemplateResponse(request, "not_found.html", {"user": user}, status_code=404)
    documents = conn.execute("SELECT * FROM documents WHERE booking_id = ? ORDER BY id", (booking_id,)).fetchall()
    return templates.TemplateResponse(request, "booking_detail.html", {
        "user": user, "b": booking_dict(booking), "events": events_for(conn, booking_id), "documents": documents,
    })


@app.get("/bookings/{booking_id}/label", response_class=HTMLResponse, include_in_schema=False)
def label_page(request: Request, booking_id: int, conn=Depends(get_db)):
    user = page_user(request, conn)
    if not user:
        return redirect_login(f"/bookings/{booking_id}/label")
    booking = load_booking(conn, booking_id)
    if not booking or not can_view(user, booking):
        return templates.TemplateResponse(request, "not_found.html", {"user": user}, status_code=404)
    return templates.TemplateResponse(request, "label.html", {"user": user, "b": booking_dict(booking)})


@app.get("/track", response_class=HTMLResponse, include_in_schema=False)
def track_page(request: Request, awb: str = "", conn=Depends(get_db)):
    return templates.TemplateResponse(request, "track.html", {"user": page_user(request, conn), "awb": awb})


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page(request: Request, conn=Depends(get_db)):
    user = page_user(request, conn)
    if not user:
        return redirect_login("/admin")
    if user["role"] != "admin":
        return templates.TemplateResponse(request, "forbidden.html", {"user": user}, status_code=403)
    return templates.TemplateResponse(request, "admin.html", {"user": user, "milestones": MILESTONES})
