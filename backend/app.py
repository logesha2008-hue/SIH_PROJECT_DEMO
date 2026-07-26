"""
Community Hall Booking and Conflict Prevention System — backend API.

Run with:  python3 app.py
Serves the API on http://localhost:5050 and also serves the static
frontend from ../frontend so the whole thing runs as one process.
"""
import sqlite3
import os
from datetime import date, datetime
from flask import Flask, request, jsonify, send_from_directory

from db import get_db, init_db, DB_PATH

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def error(msg, code=400):
    return jsonify({"error": msg}), code


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


def deposit_held(conn, booking_id):
    """Deposit currently held = sum(taken) - sum(returned), computed live
    from the transaction ledger — never stored as a balance."""
    r = conn.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN txn_type='taken' THEN amount ELSE 0 END), 0)
             - COALESCE(SUM(CASE WHEN txn_type='returned' THEN amount ELSE 0 END), 0)
             AS held
           FROM deposit_transactions WHERE booking_id = ?""",
        (booking_id,),
    ).fetchone()
    return r["held"]


def db_call(fn):
    """Wrap a handler so that a database that is briefly unreachable, or
    locked past the busy_timeout by contention, produces a clear 503
    rather than a raw stack trace reaching the client."""
    try:
        return fn()
    except sqlite3.OperationalError as e:
        return error(f"Database is temporarily unreachable, please retry: {e}", 503)


# ----------------------------------------------------------------------
# Static frontend
# ----------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


# ----------------------------------------------------------------------
# Slots
# ----------------------------------------------------------------------

@app.route("/api/slots", methods=["GET"])
def list_slots():
    def run():
        conn = get_db()
        rows = conn.execute("SELECT * FROM slots ORDER BY slot_id").fetchall()
        conn.close()
        return jsonify([row_to_dict(r) for r in rows])
    return db_call(run)


# ----------------------------------------------------------------------
# Bookings — list for a date (what the clerk sees the moment a date is
# entered), single booking detail, create, cancel
# ----------------------------------------------------------------------

@app.route("/api/bookings", methods=["GET"])
def list_bookings_for_date():
    booking_date = request.args.get("date")
    if not booking_date:
        return error("query param 'date' is required (YYYY-MM-DD)")

    def run():
        conn = get_db()
        rows = conn.execute(
            """SELECT b.booking_id, b.booking_date, b.status, b.purpose,
                      s.slot_id, s.slot_name, s.start_time, s.end_time,
                      a.name AS applicant_name
               FROM bookings b
               JOIN slots s ON s.slot_id = b.slot_id
               JOIN applicants a ON a.applicant_id = b.applicant_id
               WHERE b.booking_date = ?
               ORDER BY s.start_time""",
            (booking_date,),
        ).fetchall()
        conn.close()
        return jsonify([row_to_dict(r) for r in rows])
    return db_call(run)


@app.route("/api/bookings/<int:booking_id>", methods=["GET"])
def get_booking(booking_id):
    def run():
        conn = get_db()
        b = conn.execute(
            """SELECT b.*, s.slot_name, s.start_time, s.end_time,
                      a.name AS applicant_name, a.phone, a.address
               FROM bookings b
               JOIN slots s ON s.slot_id = b.slot_id
               JOIN applicants a ON a.applicant_id = b.applicant_id
               WHERE b.booking_id = ?""",
            (booking_id,),
        ).fetchone()
        if not b:
            conn.close()
            return error("booking not found", 404)
        held = deposit_held(conn, booking_id)
        txns = conn.execute(
            "SELECT * FROM deposit_transactions WHERE booking_id = ? ORDER BY txn_date",
            (booking_id,),
        ).fetchall()
        conn.close()
        result = row_to_dict(b)
        result["deposit_held"] = held
        result["deposit_transactions"] = [row_to_dict(t) for t in txns]
        return jsonify(result)
    return db_call(run)


@app.route("/api/bookings", methods=["POST"])
def create_booking():
    data = request.get_json(silent=True) or {}
    name = (data.get("applicant_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    booking_date = (data.get("booking_date") or "").strip()
    slot_id = data.get("slot_id")
    purpose = (data.get("purpose") or "").strip()

    # ---- server-side validation (the only kind that counts) ----
    if not name:
        return error("applicant_name is required")
    if not phone:
        return error("phone is required")
    if not slot_id:
        return error("slot_id is required")
    try:
        booking_day = datetime.strptime(booking_date, "%Y-%m-%d").date()
    except ValueError:
        return error("booking_date must be YYYY-MM-DD")
    if booking_day < date.today():
        return error("cannot book a date that has already passed")

    def run():
        conn = get_db()
        try:
            slot = conn.execute(
                "SELECT * FROM slots WHERE slot_id = ?", (slot_id,)
            ).fetchone()
            if not slot:
                conn.close()
                return error("slot_id does not exist", 404)

            # BEGIN IMMEDIATE takes the write lock right away. If a second
            # request for the same slot arrives while this transaction is
            # open, it blocks here (up to busy_timeout) instead of both
            # requests reading "free" and both writing — this is what makes
            # "exactly one of two simultaneous clerks succeeds" true.
            conn.execute("BEGIN IMMEDIATE")

            clash = conn.execute(
                """SELECT booking_id FROM bookings
                   WHERE booking_date = ? AND slot_id = ? AND status = 'confirmed'""",
                (booking_date, slot_id),
            ).fetchone()
            if clash:
                conn.rollback()
                conn.close()
                return error(
                    f"slot '{slot['slot_name']}' on {booking_date} is already booked "
                    f"(booking #{clash['booking_id']})", 409
                )

            applicant = conn.execute(
                "SELECT applicant_id FROM applicants WHERE name = ? AND phone = ?",
                (name, phone),
            ).fetchone()
            if applicant:
                applicant_id = applicant["applicant_id"]
            else:
                cur = conn.execute(
                    "INSERT INTO applicants (name, phone, address) VALUES (?, ?, ?)",
                    (name, phone, address),
                )
                applicant_id = cur.lastrowid

            cur = conn.execute(
                """INSERT INTO bookings (applicant_id, booking_date, slot_id, purpose, status)
                   VALUES (?, ?, ?, ?, 'confirmed')""",
                (applicant_id, booking_date, slot_id, purpose),
            )
            conn.commit()
            booking_id = cur.lastrowid
            conn.close()
            return jsonify({
                "booking_id": booking_id,
                "applicant_id": applicant_id,
                "booking_date": booking_date,
                "slot_id": slot_id,
                "slot_name": slot["slot_name"],
                "status": "confirmed",
            }), 201

        except sqlite3.IntegrityError:
            # Backstop: even if the pre-check above raced with another
            # transaction and both saw "free", the partial unique index on
            # (booking_date, slot_id) WHERE status='confirmed' rejects the
            # second INSERT at the database level. This is the guarantee
            # that does not depend on application code being correct.
            conn.rollback()
            conn.close()
            return error("slot was booked by another request a moment ago (rejected by database constraint)", 409)

    return db_call(run)


@app.route("/api/bookings/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    def run():
        conn = get_db()
        conn.execute("BEGIN IMMEDIATE")
        b = conn.execute(
            "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
        if not b:
            conn.rollback()
            conn.close()
            return error("booking not found", 404)
        if b["status"] == "cancelled":
            conn.rollback()
            conn.close()
            return error("booking is already cancelled")
        conn.execute(
            "UPDATE bookings SET status = 'cancelled', cancelled_at = datetime('now') WHERE booking_id = ?",
            (booking_id,),
        )
        conn.commit()
        conn.close()
        return jsonify({"booking_id": booking_id, "status": "cancelled"})
    return db_call(run)


# ----------------------------------------------------------------------
# Calendar — which slots are free/taken across a month
# ----------------------------------------------------------------------

@app.route("/api/calendar", methods=["GET"])
def calendar():
    month = request.args.get("month")  # YYYY-MM
    if not month:
        return error("query param 'month' is required (YYYY-MM)")

    def run():
        conn = get_db()
        rows = conn.execute(
            """SELECT b.booking_id, b.booking_date, b.status, b.purpose,
                      s.slot_id, s.slot_name, a.name AS applicant_name
               FROM bookings b
               JOIN slots s ON s.slot_id = b.slot_id
               JOIN applicants a ON a.applicant_id = b.applicant_id
               WHERE b.status = 'confirmed' AND substr(b.booking_date, 1, 7) = ?
               ORDER BY b.booking_date, s.start_time""",
            (month,),
        ).fetchall()
        conn.close()
        return jsonify([row_to_dict(r) for r in rows])
    return db_call(run)


# ----------------------------------------------------------------------
# Deposits
# ----------------------------------------------------------------------

@app.route("/api/deposits/take", methods=["POST"])
def deposit_take():
    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    amount = data.get("amount")
    if not booking_id or not amount or float(amount) <= 0:
        return error("booking_id and a positive amount are required")

    def run():
        conn = get_db()
        conn.execute("BEGIN IMMEDIATE")
        b = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not b:
            conn.rollback()
            conn.close()
            return error("booking not found", 404)
        conn.execute(
            "INSERT INTO deposit_transactions (booking_id, txn_type, amount) VALUES (?, 'taken', ?)",
            (booking_id, amount),
        )
        conn.commit()
        held = deposit_held(conn, booking_id)
        conn.close()
        return jsonify({"booking_id": booking_id, "deposit_held": held})
    return db_call(run)


@app.route("/api/deposits/return", methods=["POST"])
def deposit_return():
    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    amount = data.get("amount")
    if not booking_id or not amount or float(amount) <= 0:
        return error("booking_id and a positive amount are required")

    def run():
        conn = get_db()
        # BEGIN IMMEDIATE here is what stops a deposit being returned twice:
        # the held-amount check and the insert happen inside one locked
        # transaction, so a second "return" request for the same booking
        # (even fired at the same instant) sees the ledger AFTER the first
        # one has committed, not the stale figure from before it.
        conn.execute("BEGIN IMMEDIATE")
        b = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not b:
            conn.rollback()
            conn.close()
            return error("booking not found", 404)
        held = deposit_held(conn, booking_id)
        if float(amount) > held:
            conn.rollback()
            conn.close()
            return error(
                f"cannot return {amount}: only {held} is currently held for this booking "
                f"(it may already have been returned)", 409
            )
        conn.execute(
            "INSERT INTO deposit_transactions (booking_id, txn_type, amount) VALUES (?, 'returned', ?)",
            (booking_id, amount),
        )
        conn.commit()
        new_held = deposit_held(conn, booking_id)
        conn.close()
        return jsonify({"booking_id": booking_id, "deposit_held": new_held})
    return db_call(run)


@app.route("/api/deposits", methods=["GET"])
def deposits_held_list():
    def run():
        conn = get_db()
        bookings = conn.execute(
            """SELECT b.booking_id, b.booking_date, b.status, s.slot_name, a.name AS applicant_name
               FROM bookings b
               JOIN slots s ON s.slot_id = b.slot_id
               JOIN applicants a ON a.applicant_id = b.applicant_id
               ORDER BY b.booking_date"""
        ).fetchall()
        result = []
        for b in bookings:
            held = deposit_held(conn, b["booking_id"])
            if held and held > 0:
                d = row_to_dict(b)
                d["deposit_held"] = held
                result.append(d)
        conn.close()
        return jsonify(result)
    return db_call(run)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
        print(f"Initialized new database at {DB_PATH}")
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
