#!/usr/bin/env python3
# Demo seed. Names, offices and phone numbers are invented on purpose.
import os, secrets, sqlite3, sys
sys.path.insert(0, os.path.dirname(__file__))
from app import hash_pw, DB

if os.path.exists(DB):
    os.remove(DB)
conn = sqlite3.connect(DB)
conn.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, pw_hash TEXT, role TEXT);
CREATE TABLE returns (id INTEGER PRIMARY KEY, tracking TEXT UNIQUE, courier TEXT, office TEXT,
                      reason TEXT, customer_phone TEXT, day TEXT, contact_attempts INTEGER DEFAULT 0,
                      decision TEXT, decided_day TEXT, note TEXT DEFAULT '');
""")
salt = secrets.token_bytes(16)
conn.execute("INSERT INTO users VALUES (1, 'rtsdesk', ?, ?, 'supervisor')",
             (salt.hex(), hash_pw("demo1234", salt)))
salt2 = secrets.token_bytes(16)
conn.execute("INSERT INTO users VALUES (2, 'deskview', ?, ?, 'viewer')",
             (salt2.hex(), hash_pw("view1234", salt2)))
rows = [
    ("EG88213", "Karim S.", "North Gate Office", "DNR", "01000000101", "2026-10-24", 2, "reship", "Customer confirmed he will be home after 6"),
    ("EG88214", "Omar E.", "North Gate Office", "BAD_ADDRESS", "01000000102", "2026-10-24", 1, None, ""),
    ("EG88215", "Youssef A.", "Delta Lines", "REFUSED", "01000000103", "2026-10-24", 1, "back_to_seller", "Refused the parcel at the door"),
    ("EG88216", "Ali T.", "Delta Lines", "NO_CASH", "01000000104", "2026-10-24", 0, None, ""),
    ("EG88217", "Hassan M.", "Sahel Partners", "DNR", "01000000105", "2026-10-24", 3, "hold_call", "Will call us to set a time"),
    ("EG88218", "Karim S.", "North Gate Office", "DAMAGED", "01000000106", "2026-10-24", 1, "refund", "Carton crushed, photographed and uploaded"),
    ("EG88190", "Omar E.", "North Gate Office", "DNR", "01000000107", "2026-10-23", 2, "reship", ""),
    ("EG88191", "Mahmoud R.", "Sahel Partners", "BAD_ADDRESS", "01000000108", "2026-10-23", 2, "reship", "Address corrected with a landmark"),
    ("EG88192", "Ali T.", "Delta Lines", "REFUSED", "01000000109", "2026-10-23", 1, "back_to_seller", ""),
    ("EG88170", "Hassan M.", "Sahel Partners", "DNR", "01000000110", "2026-10-22", 1, "hold_call", ""),
    ("EG88171", "Youssef A.", "Delta Lines", "OTHER", "01000000111", "2026-10-22", 0, None, ""),
    ("EG88150", "Karim S.", "North Gate Office", "NO_CASH", "01000000112", "2026-10-21", 2, "reship", ""),
    ("EG88131", "Mahmoud R.", "Sahel Partners", "DNR", "01000000113", "2026-10-20", 4, "back_to_seller", "Four attempts, the customer never answers"),
    ("EG88112", "Omar E.", "North Gate Office", "REFUSED", "01000000114", "2026-10-19", 1, "refund", ""),
    ("EG88098", "Ali T.", "Delta Lines", "DAMAGED", "01000000115", "2026-10-18", 1, "refund", ""),
]
conn.executemany(
    "INSERT INTO returns (tracking,courier,office,reason,customer_phone,day,contact_attempts,decision,note) VALUES (?,?,?,?,?,?,?,?,?)",
    rows)
conn.commit(); conn.close()
print("Seeded", DB, "with", len(rows), "returns")
