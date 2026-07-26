"""
Seed the database with slots, applicants, about thirty bookings spread
across two months (including some cancellations), and deposit
transactions for several of them.

Run with: python3 seed.py
"""
import os
import sqlite3
from db import get_db, init_db, DB_PATH

SLOTS = [
    ("Morning", "08:00", "13:00"),
    ("Afternoon", "14:00", "18:00"),
    ("Evening", "18:30", "22:30"),
]

# 15 applicant families/groups
APPLICANTS = [
    ("Murugan Family", "9840011122", "12 Kamaraj St"),
    ("Lakshmi & Suresh Wedding", "9840022233", "4 Gandhi Nagar"),
    ("Panchayat Youth Committee", "9840033344", "Panchayat Office"),
    ("Devi Family", "9840044455", "7 Bharathi St"),
    ("Ramesh & Priya Wedding", "9840055566", "22 Anna Nagar"),
    ("Self Help Group - Vellalur", "9840066677", "SHG Building"),
    ("Kannan Family", "9840077788", "18 Nehru St"),
    ("Farmers Welfare Association", "9840088899", "Coop Bank Rd"),
    ("Selvi & Arjun Wedding", "9840099900", "9 Church St"),
    ("Government School - Annual Day", "9840010101", "GHS Vellalur"),
    ("Meena Family", "9840020202", "3 Market St"),
    ("Village Health Camp Committee", "9840030303", "PHC Vellalur"),
    ("Karthik & Divya Wedding", "9840040404", "15 Temple St"),
    ("Senior Citizens Club", "9840050505", "Club House"),
    ("Ganesan Family", "9840060606", "6 Station Rd"),
]

PURPOSES = [
    "Wedding", "Wedding reception", "Committee meeting", "Birthday function",
    "Annual day function", "Health camp", "Awareness meeting", "House warming",
    "Engagement", "Community meeting",
]

# (day_offset_from_month_start, slot_index, applicant_index, purpose_index, cancel?)
# Two months: 2026-08 and 2026-09. 30 bookings total, 6 of them cancelled.
BOOKINGS = [
    ("2026-08-02", 0, 1, 0, False),
    ("2026-08-02", 1, 4, 1, False),
    ("2026-08-03", 2, 2, 2, False),
    ("2026-08-05", 0, 8, 8, False),
    ("2026-08-05", 1, 8, 1, True),   # afternoon reception, later cancelled
    ("2026-08-07", 2, 13, 9, False),
    ("2026-08-08", 0, 12, 0, False),
    ("2026-08-09", 1, 12, 1, False),
    ("2026-08-10", 0, 6, 3, False),
    ("2026-08-12", 2, 11, 5, False),
    ("2026-08-14", 0, 4, 0, True),   # wedding date changed, cancelled
    ("2026-08-14", 1, 4, 1, False),  # same family, different slot, rebooked
    ("2026-08-15", 0, 9, 4, False),
    ("2026-08-16", 1, 2, 6, False),
    ("2026-08-18", 2, 0, 3, False),
    ("2026-08-20", 0, 7, 7, False),
    ("2026-08-21", 1, 3, 3, False),
    ("2026-08-22", 2, 8, 1, False),
    ("2026-08-25", 0, 5, 6, True),   # SHG meeting cancelled
    ("2026-08-27", 1, 10, 0, False),
    ("2026-08-28", 2, 14, 3, False),
    ("2026-09-01", 0, 2, 2, False),
    ("2026-09-02", 1, 13, 8, False),
    ("2026-09-03", 2, 4, 1, True),   # evening reception cancelled
    ("2026-09-05", 0, 9, 4, False),
    ("2026-09-06", 1, 9, 4, False),
    ("2026-09-08", 2, 6, 3, False),
    ("2026-09-10", 0, 3, 3, False),
    ("2026-09-12", 1, 0, 0, False),
    ("2026-09-14", 2, 12, 9, True),  # wedding postponed, cancelled
    ("2026-09-14", 0, 12, 9, False), # rebooked to morning same day
    ("2026-09-16", 1, 11, 5, False),
    ("2026-09-18", 2, 1, 1, False),
]

# deposits: (booking index in BOOKINGS list [0-based, confirmed ones only
# matter], amount taken, amount returned or None)
DEPOSITS = {
    0: (5000, None),
    1: (8000, 8000),
    2: (2000, None),
    3: (10000, None),
    6: (3000, 3000),
    8: (2000, None),
    11: (8000, None),
    13: (2500, None),
    16: (3000, 1500),
    20: (2000, 2000),
    24: (5000, None),
    27: (2000, None),
}


def seed():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    conn = get_db()

    for name, start, end in SLOTS:
        conn.execute(
            "INSERT INTO slots (slot_name, start_time, end_time) VALUES (?, ?, ?)",
            (name, start, end),
        )

    applicant_ids = []
    for name, phone, address in APPLICANTS:
        cur = conn.execute(
            "INSERT INTO applicants (name, phone, address) VALUES (?, ?, ?)",
            (name, phone, address),
        )
        applicant_ids.append(cur.lastrowid)
    conn.commit()

    slot_ids = [r["slot_id"] for r in conn.execute("SELECT slot_id FROM slots ORDER BY slot_id")]

    booking_ids = []
    for booking_date, slot_idx, app_idx, purpose_idx, cancel in BOOKINGS:
        cur = conn.execute(
            """INSERT INTO bookings (applicant_id, booking_date, slot_id, purpose, status)
               VALUES (?, ?, ?, ?, ?)""",
            (
                applicant_ids[app_idx],
                booking_date,
                slot_ids[slot_idx],
                PURPOSES[purpose_idx],
                "cancelled" if cancel else "confirmed",
            ),
        )
        booking_ids.append(cur.lastrowid)
        if cancel:
            conn.execute(
                "UPDATE bookings SET cancelled_at = datetime('now') WHERE booking_id = ?",
                (cur.lastrowid,),
            )
    conn.commit()

    for idx, (taken, returned) in DEPOSITS.items():
        bid = booking_ids[idx]
        conn.execute(
            "INSERT INTO deposit_transactions (booking_id, txn_type, amount) VALUES (?, 'taken', ?)",
            (bid, taken),
        )
        if returned:
            conn.execute(
                "INSERT INTO deposit_transactions (booking_id, txn_type, amount) VALUES (?, 'returned', ?)",
                (bid, returned),
            )
    conn.commit()
    conn.close()

    print(f"Seeded {len(SLOTS)} slots, {len(APPLICANTS)} applicants, "
          f"{len(BOOKINGS)} bookings ({sum(1 for b in BOOKINGS if b[4])} cancelled), "
          f"{len(DEPOSITS)} bookings with deposit activity.")


if __name__ == "__main__":
    seed()
