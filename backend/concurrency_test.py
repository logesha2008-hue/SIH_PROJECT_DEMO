"""
Fires two booking requests for the SAME date+slot at the same moment
(via a thread barrier so neither request gets a head start) against a
running server, and prints both raw responses.

This is the "two clerks at the same counter" scenario from Task 5:
exactly one request must succeed (201) and the other must be refused (409).

Usage:
    python3 app.py                 # in one terminal, server must be running
    python3 concurrency_test.py    # in another terminal
"""
import threading
import requests
import sys
from datetime import date, timedelta

URL = "http://localhost:5050/api/bookings"

# Pick a fresh future booking date so the demo doesn't collide with any
# earlier seed or test data.
BOOKING_DATE = (date.today() + timedelta(days=200)).strftime("%Y-%m-%d")

PAYLOAD = {
    "applicant_name": None,   # filled per-thread below
    "phone": "9999911111",
    "booking_date": BOOKING_DATE,
    "slot_id": 2,
    "purpose": "Concurrency test booking",
}

results = {}
barrier = threading.Barrier(2)


def fire(clerk_name, key):
    payload = dict(PAYLOAD)
    payload["applicant_name"] = clerk_name
    barrier.wait()  # both threads release at (almost) the exact same instant
    resp = requests.post(URL, json=payload)
    results[key] = (resp.status_code, resp.text)


def main():
    t1 = threading.Thread(target=fire, args=("Clerk Counter A booking", "clerk_A"))
    t2 = threading.Thread(target=fire, args=("Clerk Counter B booking", "clerk_B"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print("=== Two simultaneous requests for 2026-10-10, Afternoon slot ===\n")
    for key in ("clerk_A", "clerk_B"):
        code, body = results[key]
        print(f"{key}: HTTP {code}\n  {body}\n")

    codes = sorted(code for code, _ in results.values())
    if codes == [201, 409]:
        print("RESULT: exactly one request succeeded (201) and the other was refused (409). PASS")
    else:
        print(f"RESULT: unexpected outcome, status codes were {codes}. FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
