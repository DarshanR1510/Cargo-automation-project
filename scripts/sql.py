"""Run SQL against the app database without installing anything.

Usage:
  python scripts/sql.py "SELECT status, COUNT(*) FROM bookings GROUP BY status"
  python scripts/sql.py            (interactive, type queries, end with ;)
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "cargo.db"


def run(conn, sql):
    try:
        cur = conn.execute(sql)
    except sqlite3.Error as exc:
        print(f"ERROR: {exc}")
        return
    if cur.description is None:
        conn.commit()
        print(f"OK, {cur.rowcount} rows affected")
        return
    headers = [d[0] for d in cur.description]
    rows = cur.fetchall()
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    line = " | ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print(" | ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    print(f"({len(rows)} rows)")


def main():
    if not DB.exists():
        sys.exit("Database not found. Start the app once with: python run.py")
    conn = sqlite3.connect(DB)
    if len(sys.argv) > 1:
        run(conn, " ".join(sys.argv[1:]))
        return
    print("SQLite shell. End each query with ; and press Enter. Ctrl+C to quit.")
    buffer = ""
    while True:
        try:
            buffer += input("sql> " if not buffer else "...> ") + "\n"
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if buffer.strip().endswith(";"):
            run(conn, buffer)
            buffer = ""


if __name__ == "__main__":
    main()
