#!/usr/bin/env python3
# RTS returns manager. The parcels that came back tonight, and what we decided about each one.
# Small API on purpose. One file, sqlite, nothing to install.
import csv, hashlib, hmac, io, json, logging, logging.handlers, os, re, secrets, sqlite3, time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8081"))
DB = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "rts.db")
LOG_PATH = os.environ.get("LOG_PATH") or os.path.join(BASE_DIR, "rts.log")
BACKUP_DIR = os.environ.get("BACKUP_DIR") or os.path.join(BASE_DIR, "backups")
IMPORT_LIMIT = 500_000
TOKENS = {}
TOKEN_TTL = 8 * 3600
ADMIN_ROLES = ("supervisor",)

REASONS = ("DNR", "REFUSED", "BAD_ADDRESS", "DAMAGED", "NO_CASH", "OTHER")
DECISIONS = ("reship", "hold_call", "back_to_seller", "refund")
IMPORT_COLUMNS = ("tracking", "courier", "office", "reason", "day")

log = logging.getLogger("rts")
if not log.handlers:
    try:
        handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=256_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    except OSError:
        log.addHandler(logging.NullHandler())

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000).hex()

def valid_date(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False

def day_range(start, end):
    first = date.fromisoformat(start)
    days = (date.fromisoformat(end) - first).days
    return [(first + timedelta(days=i)).isoformat() for i in range(days + 1)]

class H(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, err_code, message, **extra):
        payload = {"ok": False, "error": {"code": err_code, "message": message}}
        payload.update(extra)
        log.warning("request failed code=%s status=%s path=%s", err_code, code, urlparse(self.path).path)
        return self._send(code, payload)

    def _session(self):
        tok = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        s = TOKENS.get(tok)
        return s if s and s["expires"] > time.time() else None

    def _auth(self):
        s = self._session()
        return s["user"] if s else None

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20000:
            return None
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return None

    def _raw_body(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            return None
        return self.rfile.read(n)

    def do_POST(self):
        try:
            self._post()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("unhandled error on POST %s", self.path)
            try:
                self._send(500, {"ok": False, "error": {"code": "server_error", "message": "something broke on the server, the log has the details"}})
            except Exception:
                pass

    def _post(self):
        path = urlparse(self.path).path
        if path == "/api/import":
            return self._import()
        if path == "/api/admin/backup":
            return self._backup()
        data = self._body()
        if data is None:
            return self._err(400, "bad_body", "request body is not valid json or is too large")
        if path == "/api/login":
            user = str(data.get("username", ""))[:40]
            pw = str(data.get("password", ""))[:100]
            conn = db()
            row = conn.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
            conn.close()
            if not row or not hmac.compare_digest(hash_pw(pw, bytes.fromhex(row["salt"])), row["pw_hash"]):
                return self._err(401, "bad_credentials", "wrong username or password")
            tok = secrets.token_urlsafe(32)
            TOKENS[tok] = {"user": user, "role": row["role"], "expires": time.time() + TOKEN_TTL}
            log.info("login user=%s", user)
            return self._send(200, {"token": tok, "user": user, "role": row["role"]})
        if not self._auth():
            return self._err(401, "login_required", "login required")
        conn = db()
        if path == "/api/returns":
            tracking = str(data.get("tracking", "")).strip()[:40]
            courier = str(data.get("courier", "")).strip()[:60]
            office = str(data.get("office", "")).strip()[:60]
            reason = str(data.get("reason", "")).strip()
            day = str(data.get("day", "")).strip()
            phone = str(data.get("customer_phone", "")).strip()[:20]
            if not tracking or not courier or not office or reason not in REASONS or not valid_date(day):
                conn.close()
                return self._err(400, "validation", "tracking, courier, office, a valid reason and day are required")
            try:
                cur = conn.execute(
                    "INSERT INTO returns (tracking,courier,office,reason,customer_phone,day) VALUES (?,?,?,?,?,?)",
                    (tracking, courier, office, reason, phone, day))
                conn.commit()
                new_id = cur.lastrowid
            except sqlite3.IntegrityError:
                conn.close()
                return self._err(409, "duplicate_tracking", "tracking already logged")
            conn.close()
            return self._send(201, {"ok": True, "id": new_id})
        m = re.fullmatch(r"/api/returns/(\d+)/(decision|contact)", path)
        if m:
            rid = int(m.group(1))
            row = conn.execute("SELECT * FROM returns WHERE id=?", (rid,)).fetchone()
            if not row:
                conn.close()
                return self._err(404, "not_found", "not found")
            if m.group(2) == "contact":
                # every call is counted on the record, so nobody can claim one that is not there
                conn.execute("UPDATE returns SET contact_attempts = contact_attempts + 1 WHERE id=?", (rid,))
                conn.commit(); conn.close()
                return self._send(200, {"ok": True, "contact_attempts": row["contact_attempts"] + 1})
            decision = str(data.get("decision", "")).strip()
            note = str(data.get("note", "")).strip()[:400]
            if decision not in DECISIONS:
                conn.close()
                return self._err(400, "validation", "decision must be one of the workflow decisions")
            # no reship without at least one logged contact attempt, that is a station rule
            if decision == "reship" and row["contact_attempts"] < 1:
                conn.close()
                return self._err(400, "reship_needs_contact", "reship needs at least one logged customer contact first")
            conn.execute("UPDATE returns SET decision=?, decided_day=date('now'), note=? WHERE id=?",
                         (decision, note, rid))
            conn.commit(); conn.close()
            return self._send(200, {"ok": True})
        conn.close()
        return self._err(404, "not_found", "not found")

    def _import(self):
        if not self._auth():
            return self._err(401, "login_required", "login required")
        raw = self._raw_body(IMPORT_LIMIT)
        if raw is None:
            return self._err(413, "import_too_large", f"csv body is over the {IMPORT_LIMIT} byte limit")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return self._err(400, "bad_encoding", "csv must be utf-8 text")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            return self._err(400, "missing_columns", "csv has no header row", missing=list(IMPORT_COLUMNS))
        headers = [(h or "").strip().lower() for h in reader.fieldnames]
        missing = [c for c in IMPORT_COLUMNS if c not in headers]
        if missing:
            return self._err(400, "missing_columns", "csv is missing required columns", missing=missing)
        inserted = 0
        skipped = []
        rejected = []
        conn = db()
        seen = {r[0] for r in conn.execute("SELECT tracking FROM returns")}
        total = 0
        for lineno, raw_row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
            if not any(row.values()):
                continue
            total += 1
            tracking = row.get("tracking", "")[:40]
            courier = row.get("courier", "")[:60]
            office = row.get("office", "")[:60]
            reason = row.get("reason", "")
            day = row.get("day", "")
            phone = row.get("customer_phone", "")[:20]
            problem = None
            if not tracking:
                problem = "tracking is empty"
            elif not courier:
                problem = "courier is empty"
            elif not office:
                problem = "office is empty"
            elif reason not in REASONS:
                problem = f"reason {reason!r} is not one of {', '.join(REASONS)}"
            elif not valid_date(day):
                problem = f"day {day!r} is not a real YYYY-MM-DD date"
            if problem:
                rejected.append({"row": lineno, "tracking": tracking, "reason": problem})
                continue
            if tracking in seen:
                skipped.append(tracking)
                continue
            conn.execute(
                "INSERT INTO returns (tracking,courier,office,reason,customer_phone,day) VALUES (?,?,?,?,?,?)",
                (tracking, courier, office, reason, phone, day))
            seen.add(tracking)
            inserted += 1
        conn.commit(); conn.close()
        log.info("csv import inserted=%s skipped=%s rejected=%s", inserted, len(skipped), len(rejected))
        return self._send(200, {"ok": True, "inserted": inserted, "skipped_duplicates": skipped,
                                "rejected_rows": rejected, "total_rows": total})

    def _backup(self):
        session = self._session()
        if not session:
            return self._err(401, "login_required", "login required")
        if session["role"] not in ADMIN_ROLES:
            return self._err(403, "admin_only", "backup is limited to the supervisor account")
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = f"rts-backup-{stamp}.db"
        dest = os.path.join(BACKUP_DIR, name)
        counter = 1
        while os.path.exists(dest):
            counter += 1
            name = f"rts-backup-{stamp}-{counter}.db"
            dest = os.path.join(BACKUP_DIR, name)
        src = db()
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close(); src.close()
        size = os.path.getsize(dest)
        log.info("backup written name=%s bytes=%s by=%s", name, size, session["user"])
        return self._send(200, {"ok": True, "backup": name, "size": size})

    def do_GET(self):
        try:
            self._get()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("unhandled error on GET %s", self.path)
            try:
                self._send(500, {"ok": False, "error": {"code": "server_error", "message": "something broke on the server, the log has the details"}})
            except Exception:
                pass

    def _get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            fpath = os.path.join(BASE_DIR, "..", "frontend", "index.html")
            with open(fpath, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return self.wfile.write(body)
        if not path.startswith("/api/"):
            return self._err(404, "not_found", "not found")
        if not self._auth():
            return self._err(401, "login_required", "login required")
        q = parse_qs(parsed.query)
        conn = db()
        if path == "/api/board":
            day = (q.get("day") or [""])[0]
            if not valid_date(day):
                conn.close()
                return self._err(400, "validation", "day is required, format YYYY-MM-DD")
            rows = [dict(r) for r in conn.execute("SELECT * FROM returns WHERE day=? ORDER BY id", (day,))]
            by_reason = {}
            for r in rows:
                by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
            payload = {
                "day": day,
                "total": len(rows),
                "waiting_decision": sum(1 for r in rows if not r["decision"]),
                "by_reason": by_reason,
                "returns": rows,
            }
        elif path == "/api/report":
            start = (q.get("from") or [""])[0]
            end = (q.get("to") or [""])[0]
            if not valid_date(start) or not valid_date(end) or start > end:
                conn.close()
                return self._err(400, "validation", "from and to are required as YYYY-MM-DD, from before to")
            if (date.fromisoformat(end) - date.fromisoformat(start)).days > 62:
                conn.close()
                return self._err(400, "validation", "report range is capped at 63 days")
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM returns WHERE day BETWEEN ? AND ? ORDER BY day, id", (start, end))]
            by_reason = {}
            by_decision = {}
            per_day = {}
            for r in rows:
                by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
                key = r["decision"] or "waiting"
                by_decision[key] = by_decision.get(key, 0) + 1
                slot = per_day.setdefault(r["day"], {"day": r["day"], "total": 0, "waiting": 0})
                slot["total"] += 1
                if not r["decision"]:
                    slot["waiting"] += 1
            trend = [per_day.get(d, {"day": d, "total": 0, "waiting": 0}) for d in day_range(start, end)]
            payload = {"from": start, "to": end, "total": len(rows),
                       "waiting_decision": sum(1 for r in rows if not r["decision"]),
                       "by_reason": by_reason, "by_decision": by_decision, "trend": trend}
        elif path == "/api/returns":
            sql = "SELECT * FROM returns WHERE 1=1"
            args = []
            day = (q.get("day") or [""])[0]
            needle = (q.get("q") or [""])[0].strip()[:60]
            status = (q.get("status") or [""])[0]
            if valid_date(day):
                sql += " AND day=?"; args.append(day)
            if needle:
                sql += " AND (tracking LIKE ? OR courier LIKE ? OR office LIKE ?)"
                args += [f"%{needle}%"] * 3
            if status == "waiting":
                sql += " AND decision IS NULL"
            elif status in DECISIONS:
                sql += " AND decision=?"; args.append(status)
            sql += " ORDER BY day DESC, id DESC LIMIT 300"
            payload = {"returns": [dict(r) for r in conn.execute(sql, args)]}
        else:
            conn.close()
            return self._err(404, "not_found", "not found")
        conn.close()
        return self._send(200, payload)

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    print(f"RTS returns manager on http://127.0.0.1:{PORT}")
    log.info("starting on port %s db=%s", PORT, DB)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
