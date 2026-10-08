"""Builds a fresh database with realistic cargo data.

The seed is deterministic (fixed random seed) so your tests and SQL answers
give the same results every time you reset.

It also contains a few "legacy import" data problems on purpose, for SQL practice.
"""
import random
import shutil
from datetime import datetime, timedelta

from app.db import DB_PATH, SCHEMA, UPLOAD_DIR, connect
from app.domain import MILESTONES, calc_weights, make_awb

USERS = [
    (1, "admin", "Admin@123", "admin", "Cargo Ops Admin", "ops@cargo-lab.test"),
    (2, "acme", "Acme@123", "customer", "Acme Freight Forwarders", "bookings@acme.test"),
    (3, "globex", "Globex@123", "customer", "Globex Logistics", "desk@globex.test"),
]

AIRPORTS = [
    ("AUH", "Zayed International", "Abu Dhabi", "UAE"),
    ("DXB", "Dubai International", "Dubai", "UAE"),
    ("BOM", "Chhatrapati Shivaji Maharaj International", "Mumbai", "India"),
    ("DEL", "Indira Gandhi International", "Delhi", "India"),
    ("AMD", "Sardar Vallabhbhai Patel International", "Ahmedabad", "India"),
    ("LHR", "Heathrow", "London", "United Kingdom"),
    ("FRA", "Frankfurt am Main", "Frankfurt", "Germany"),
    ("CDG", "Charles de Gaulle", "Paris", "France"),
    ("JFK", "John F. Kennedy International", "New York", "USA"),
    ("ORD", "O'Hare International", "Chicago", "USA"),
    ("SIN", "Changi", "Singapore", "Singapore"),
    ("HKG", "Hong Kong International", "Hong Kong", "China"),
]

COMMODITIES = [
    ("Textiles", "GEN"), ("Auto parts", "GEN"), ("Electronics", "GEN"),
    ("Pharmaceuticals", "PIL"), ("Fresh flowers", "PER"), ("Seafood", "PER"),
    ("Lithium batteries", "DGR"), ("Machinery spares", "GEN"), ("Live poultry", "AVI"),
    ("Documents", "GEN"), ("Spices", "GEN"), ("Paint samples", "DGR"),
]


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def reset_database() -> None:
    rnd = random.Random(42)
    conn = connect()
    cur = conn.cursor()
    for table in ("users", "airports", "bookings", "tracking_events", "documents", "tokens"):
        cur.execute(f"DROP TABLE IF EXISTS {table}")
    cur.executescript(SCHEMA)
    cur.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", USERS)
    cur.executemany("INSERT INTO airports VALUES (?,?,?,?)", AIRPORTS)

    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    codes = [a[0] for a in AIRPORTS]
    serial = 1000000

    for i in range(36):
        serial += rnd.randint(1, 40)
        customer_id = 2 if i % 2 == 0 else 3
        origin = "AUH" if rnd.random() < 0.55 else rnd.choice(codes)
        destination = rnd.choice([c for c in codes if c != origin])
        commodity, handling = rnd.choice(COMMODITIES)
        pieces = rnd.randint(1, 40)
        weight = round(rnd.uniform(5, 2500), 1)
        dims = [rnd.choice([40, 60, 80, 100, 120, 150]) for _ in range(3)]
        volumetric, chargeable = calc_weights(weight, *dims, buggy=False)
        created = now - timedelta(days=rnd.randint(1, 30), hours=rnd.randint(0, 23))
        flight = created + timedelta(days=rnd.randint(1, 6))

        # How far along the journey this shipment is
        progress = rnd.choice([0, 0, 1, 2, 3, 4, 5, 6, 7, 7, 7])
        if flight.date() > now.date():
            progress = min(progress, 1)
        cancelled = progress == 0 and rnd.random() < 0.35
        status = "CAN" if cancelled else MILESTONES[progress]

        cur.execute(
            """INSERT INTO bookings (awb_number, customer_id, origin, destination, pieces,
               weight_kg, length_cm, width_cm, height_cm, volumetric_kg, chargeable_kg,
               commodity, special_handling, flight_date, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (make_awb(serial), customer_id, origin, destination, pieces, weight, *dims,
             volumetric, chargeable, commodity, handling, flight.date().isoformat(),
             status, iso(created), iso(created)),
        )
        booking_id = cur.lastrowid

        # Tracking events, in order, at plausible times
        t = created
        for step in range(progress + 1):
            milestone = MILESTONES[step]
            if step >= 2:
                t = max(t, flight - timedelta(hours=6)) + timedelta(hours=rnd.randint(2, 10))
            else:
                t = t + timedelta(hours=rnd.randint(1, 20)) if step else t
            location = destination if step >= 4 else origin
            # Legacy bug reproduced in old data: DGR bookings never got their BKD event
            if milestone == "BKD" and handling == "DGR":
                continue
            cur.execute(
                "INSERT INTO tracking_events (booking_id, milestone, location, event_time, remarks) VALUES (?,?,?,?,?)",
                (booking_id, milestone, location, iso(t), None),
            )
        if cancelled:
            cur.execute(
                "INSERT INTO tracking_events (booking_id, milestone, location, event_time, remarks) VALUES (?,?,?,?,?)",
                (booking_id, "CAN", origin, iso(created + timedelta(hours=3)), "Cancelled by customer"),
            )
        cur.execute("UPDATE bookings SET updated_at = ? WHERE id = ?", (iso(t), booking_id))

    # ---- Legacy import anomalies, for SQL practice ----
    first = cur.execute("SELECT * FROM bookings ORDER BY id LIMIT 1").fetchone()
    cols = [d[0] for d in cur.description][1:]
    values = list(first)[1:]
    # 1. Duplicate AWB (same AWB imported twice)
    cur.execute(f"INSERT INTO bookings ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", values)
    # 2. Orphan booking whose customer does not exist
    values_orphan = values.copy()
    values_orphan[cols.index("awb_number")] = make_awb(serial + 77)
    values_orphan[cols.index("customer_id")] = 99
    cur.execute(f"INSERT INTO bookings ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", values_orphan)
    # 3. Booking marked delivered but its DLV event is missing
    dlv = cur.execute("SELECT id FROM bookings WHERE status = 'DLV' ORDER BY id LIMIT 1").fetchone()
    if dlv:
        cur.execute("DELETE FROM tracking_events WHERE booking_id = ? AND milestone = 'DLV'", (dlv[0],))
    # 4. Missing commodity
    cur.execute("UPDATE bookings SET commodity = NULL WHERE id = (SELECT id FROM bookings WHERE status = 'BKD' ORDER BY id LIMIT 1)")

    conn.commit()
    conn.close()


def ensure_database() -> None:
    if not DB_PATH.exists():
        reset_database()
        return
    conn = connect()
    try:
        conn.execute("SELECT 1 FROM bookings LIMIT 1")
    except Exception:
        conn.close()
        reset_database()
        return
    conn.close()


if __name__ == "__main__":
    reset_database()
    print(f"Database reset at {DB_PATH}")
