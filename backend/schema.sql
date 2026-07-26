-- Community Hall Booking System — Schema
-- SQLite. Foreign keys are enforced at connection time (see db.py: PRAGMA foreign_keys = ON).

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------
-- APPLICANTS: the people/families who request the hall
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS applicants (
    applicant_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    phone         TEXT NOT NULL,
    address       TEXT
);

-- ------------------------------------------------------------------
-- SLOTS: the fixed divisions of a day. Storing named slots instead of
-- free-text time is what lets the database compare two bookings and
-- detect a clash, instead of a human reading two rows of text.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS slots (
    slot_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_name   TEXT NOT NULL UNIQUE,
    start_time  TEXT NOT NULL,   -- HH:MM, 24h
    end_time    TEXT NOT NULL
);

-- ------------------------------------------------------------------
-- BOOKINGS: one row per booking attempt on a date+slot.
-- status moves confirmed -> cancelled. A cancelled booking stays in
-- the table (nothing is deleted) but no longer counts as occupying
-- the slot.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookings (
    booking_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  INTEGER NOT NULL REFERENCES applicants(applicant_id),
    booking_date  TEXT NOT NULL,               -- YYYY-MM-DD
    slot_id       INTEGER NOT NULL REFERENCES slots(slot_id),
    purpose       TEXT,
    status        TEXT NOT NULL DEFAULT 'confirmed'
                       CHECK (status IN ('confirmed', 'cancelled')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    cancelled_at  TEXT
);

-- THE CLASH RULE, enforced by the database itself:
-- a partial unique index that only counts CONFIRMED bookings.
-- Two confirmed rows for the same (date, slot) cannot both exist —
-- SQLite raises IntegrityError on the second INSERT.
-- A cancelled row is excluded from the index, so the slot frees up
-- for rebooking automatically. This is enforced even if the
-- application code has a bug, because it lives in the database, not
-- in the Flask route.
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_booking_per_slot
    ON bookings (booking_date, slot_id)
    WHERE status = 'confirmed';

-- ------------------------------------------------------------------
-- DEPOSIT_TRANSACTIONS: append-only ledger. The "deposit held" figure
-- is always CALCULATED as sum(taken) - sum(returned) for a booking,
-- never stored as a balance column, so it cannot drift from what
-- actually happened.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deposit_transactions (
    transaction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id      INTEGER NOT NULL REFERENCES bookings(booking_id),
    txn_type        TEXT NOT NULL CHECK (txn_type IN ('taken', 'returned')),
    amount          REAL NOT NULL CHECK (amount > 0),
    txn_date        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(booking_date);
CREATE INDEX IF NOT EXISTS idx_deposit_booking ON deposit_transactions(booking_id);
