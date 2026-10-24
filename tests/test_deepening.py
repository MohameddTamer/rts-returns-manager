#!/usr/bin/env python3
# Deepening checks for the RTS manager. Run: python3 tests/test_deepening.py
# Boots the real server on its own port against a throwaway database in a temp folder.
import json, os, sqlite3, subprocess, sys, tempfile, time, urllib.request, urllib.error

ROOT = os.path.join(os.path.dirname(__file__), "..")
PORT = "8191"
BASE = f"http://127.0.0.1:{PORT}"
CHECKS = 0

def check(cond, msg):
    global CHECKS
    CHECKS += 1
    if not cond:
        raise AssertionError(f"check {CHECKS} failed: {msg}")
    print(f"ok {CHECKS}: {msg}")

def call(method, path, body=None, token=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, method=method, data=data,
        headers={"Content-Type": ctype, **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            payload = r.read()
            return r.status, json.loads(payload or b"{}") if ctype == "application/json" or r.headers.get_content_type() == "application/json" else payload
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload or b"{}")
        except json.JSONDecodeError:
            return e.code, {}

def wait_up():
    for _ in range(50):
        try:
            with urllib.request.urlopen(BASE + "/", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False

GOOD_CSV = (
    "tracking,courier,office,reason,day,customer_phone\n"
    "IMP1001,Test D.,Delta Lines,DNR,2026-10-24,01000000201\n"
    "IMP1002,Test E.,North Gate Office,REFUSED,2026-10-24,01000000202\n"
)
MIXED_CSV = (
    "tracking,courier,office,reason,day,customer_phone\n"
    "IMP1003,Test D.,Delta Lines,NO_CASH,2026-10-24,01000000203\n"
    "IMP1004,Test D.,Delta Lines,LOST_IN_SPACE,2026-10-24,01000000204\n"
    ",Test D.,Delta Lines,DNR,2026-10-24,01000000205\n"
    "IMP1005,Test D.,Delta Lines,DNR,2026-13-40,01000000206\n"
    "EG88213,Test D.,Delta Lines,DNR,2026-10-24,01000000207\n"
)

def main():
    tmp = tempfile.mkdtemp(prefix="rts-deep-")
    db_path = os.path.join(tmp, "deep.db")
    log_path = os.path.join(tmp, "deep.log")
    backup_dir = os.path.join(tmp, "backups")
    env = dict(os.environ, PORT=PORT, DB_PATH=db_path, LOG_PATH=log_path, BACKUP_DIR=backup_dir)
    subprocess.run([sys.executable, "seed.py"], cwd=os.path.join(ROOT, "backend"), env=env, check=True)
    srv = subprocess.Popen([sys.executable, "app.py"], cwd=os.path.join(ROOT, "backend"), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        check(wait_up(), "server boots on the PORT from the environment")
        check(os.path.exists(db_path), "seed wrote the database at the DB_PATH from the environment")

        code, body = call("GET", "/api/board?day=2026-10-24")
        check(code == 401, "board without a token is 401")
        check(isinstance(body.get("error"), dict), "unauthenticated error is a structured object")
        check(body["error"].get("code") == "login_required", "unauthenticated error names its code")
        check(bool(body["error"].get("message")), "unauthenticated error carries a message")

        code, viewer = call("POST", "/api/login", {"username": "deskview", "password": "view1234"})
        check(code == 200 and viewer.get("role") == "viewer", "viewer account logs in with the viewer role")
        code, body = call("POST", "/api/admin/backup", {}, token=viewer["token"])
        check(code == 403, "viewer cannot take a backup")
        check(body["error"].get("code") == "admin_only", "backup refusal names the admin_only code")

        code, body = call("POST", "/api/login", {"username": "rtsdesk", "password": "demo1234"})
        check(code == 200, "supervisor logs in")
        tok = body["token"]

        code, rep = call("GET", "/api/report?from=2026-10-18&to=2026-10-24", token=tok)
        check(code == 200, "report answers for a week range")
        check(all(k in rep for k in ("from", "to", "total", "by_reason", "by_decision", "trend")), "report has the documented shape")
        check(rep["from"] == "2026-10-18" and rep["to"] == "2026-10-24", "report echoes its range")
        check(len(rep["trend"]) == 7, "trend covers every day in the range including quiet ones")
        check(all("day" in t and "total" in t and "waiting" in t for t in rep["trend"]), "every trend entry carries day, total and waiting")
        check(rep["total"] == 15, "report total matches the seeded returns")
        check(rep["by_reason"].get("DNR", 0) >= 4, "by_reason counts the seeded DNR returns")
        check(sum(rep["by_reason"].values()) == rep["total"], "by_reason adds up to the report total")
        code, body = call("GET", "/api/report?from=2026-10-24&to=2026-10-18", token=tok)
        check(code == 400 and body["error"].get("code") == "validation", "backwards report range is a structured 400")
        code, body = call("GET", "/api/nope", token=tok)
        check(code == 404 and body["error"].get("code") == "not_found", "unknown api path is a structured 404")

        code, body = call("POST", "/api/import", raw=GOOD_CSV.encode(), ctype="text/csv")
        check(code == 401, "import without a token is 401")

        code, rep1 = call("POST", "/api/import", raw=GOOD_CSV.encode(), token=tok, ctype="text/csv")
        check(code == 200, "clean csv import succeeds")
        check(rep1["inserted"] == 2, "clean import inserts both rows")
        check(rep1["skipped_duplicates"] == [], "clean import skips nothing")
        check(rep1["rejected_rows"] == [], "clean import rejects nothing")
        check(rep1["total_rows"] == 2, "import report counts the data rows")
        code, rows = call("GET", "/api/returns?q=IMP100", token=tok)
        check(len(rows["returns"]) == 2, "imported returns are searchable afterwards")

        code, rep2 = call("POST", "/api/import", raw=GOOD_CSV.encode(), token=tok, ctype="text/csv")
        check(code == 200, "repeating the same import still answers")
        check(rep2["inserted"] == 0, "repeated import inserts nothing twice")
        check(sorted(rep2["skipped_duplicates"]) == ["IMP1001", "IMP1002"], "duplicates are named by tracking number")

        code, rep3 = call("POST", "/api/import", raw=MIXED_CSV.encode(), token=tok, ctype="text/csv")
        check(code == 200, "mixed csv import answers with a report instead of failing whole")
        check(rep3["inserted"] == 1, "the one valid row in the mixed file is inserted")
        check(rep3["skipped_duplicates"] == ["EG88213"], "a tracking that already exists is named as a duplicate")
        check(len(rep3["rejected_rows"]) == 3, "the three broken rows are all rejected, none swallowed")
        check(all(isinstance(r["row"], int) and r["row"] >= 2 for r in rep3["rejected_rows"]), "rejected rows carry their csv line number")
        check(all(r["reason"] for r in rep3["rejected_rows"]), "every rejected row says why")
        check(any("reason" in r["reason"] for r in rep3["rejected_rows"]), "the invented reason code is called out")
        check(any("day" in r["reason"] for r in rep3["rejected_rows"]), "the impossible date is called out")
        check(any("tracking" in r["reason"] for r in rep3["rejected_rows"]), "the empty tracking is called out")

        code, body = call("POST", "/api/import", raw=b"tracking,courier\nX1,Test D.\n", token=tok, ctype="text/csv")
        check(code == 400, "a csv missing required columns is refused")
        check(body["error"].get("code") == "missing_columns", "missing columns error names its code")
        check("reason" in body.get("missing", []) and "day" in body.get("missing", []), "the missing column names are listed")

        code, body = call("POST", "/api/admin/backup", {}, token=tok)
        check(code == 200, "supervisor backup succeeds")
        name = body.get("backup", "")
        check(name.startswith("rts-backup-") and name.endswith(".db"), "backup name is timestamped and named in the reply")
        dest = os.path.join(backup_dir, name)
        check(os.path.exists(dest), "the backup file exists in the configured BACKUP_DIR")
        check(body.get("size") == os.path.getsize(dest) and body["size"] > 0, "reported backup size matches the file")
        bconn = sqlite3.connect(dest)
        integrity = bconn.execute("PRAGMA integrity_check").fetchone()[0]
        backup_count = bconn.execute("SELECT COUNT(*) FROM returns").fetchone()[0]
        bconn.close()
        check(integrity == "ok", "backup database passes integrity_check")
        live = sqlite3.connect(db_path)
        live_count = live.execute("SELECT COUNT(*) FROM returns").fetchone()[0]
        live.close()
        check(backup_count == live_count, "backup holds every return the live database holds")

        check(os.path.exists(log_path) and os.path.getsize(log_path) > 0, "the app wrote its rotating log file at LOG_PATH")
        with open(log_path, encoding="utf-8") as fh:
            log_text = fh.read()
        check("backup" in log_text or "import" in log_text, "the log recorded the import or backup work")

        print(f"RTS deepening tests passed ({CHECKS} checks)")
    finally:
        srv.terminate()

if __name__ == "__main__":
    main()
