import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "hall.db")


def get_db():
    """
    Open a connection to the SQLite database.

    busy_timeout makes SQLite wait (instead of failing instantly) if another
    connection is mid-transaction — this is what makes the "two clerks at the
    same moment" case resolve as one-wins/one-refused instead of a raw lock
    error. If the database file itself is unreachable (e.g. disk removed,
    permissions revoked, path bad) sqlite3.OperationalError is raised here,
    which every route catches and turns into HTTP 503.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
