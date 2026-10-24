#!/usr/bin/env python3
# End to end check for the RTS api. Run: python3 tests/test_api.py
# It seeds a scratch copy, boots the server on 8091 and walks the real workflow.
import json, os, shutil, subprocess, sys, time, urllib.request, urllib.error

ROOT = os.path.join(os.path.dirname(__file__), "..")
PORT = "8091"
BASE = f"http://127.0.0.1:{PORT}"

def call(method, path, body=None, token=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

def main():
    env = dict(os.environ, PORT=PORT)
    subprocess.run([sys.executable, "seed.py"], cwd=os.path.join(ROOT, "backend"), check=True)
    srv = subprocess.Popen([sys.executable, "app.py"], cwd=os.path.join(ROOT, "backend"), env=env)
    try:
        time.sleep(1.2)
        code, _ = call("GET", "/api/board?day=2026-10-24")
        assert code == 401, f"no token should be 401, got {code}"
        code, _ = call("POST", "/api/login", {"username": "rtsdesk", "password": "nope"})
        assert code == 401, f"wrong password should be 401, got {code}"
        code, body = call("POST", "/api/login", {"username": "rtsdesk", "password": "demo1234"})
        assert code == 200, body
        tok = body["token"]
        code, board = call("GET", "/api/board?day=2026-10-24", token=tok)
        assert code == 200 and board["total"] == 6, board
        assert board["waiting_decision"] == 2, board
        assert board["by_reason"].get("DNR") == 2, board
        code, rows = call("GET", "/api/returns?status=waiting", token=tok)
        waiting = rows["returns"]
        assert len(waiting) == 3, waiting
        target = [r for r in waiting if r["day"] == "2026-10-24" and r["contact_attempts"] == 0][0]
        code, body = call("POST", f"/api/returns/{target['id']}/decision",
                          {"decision": "reship", "note": "x"}, token=tok)
        assert code == 400, "reship without any contact must be refused"
        code, body = call("POST", f"/api/returns/{target['id']}/contact", {}, token=tok)
        assert code == 200 and body["contact_attempts"] == 1, body
        code, body = call("POST", f"/api/returns/{target['id']}/decision",
                          {"decision": "reship", "note": "address fixed with the customer"}, token=tok)
        assert code == 200, body
        code, body = call("POST", f"/api/returns/{target['id']}/decision",
                          {"decision": "fly_it_out", "note": ""}, token=tok)
        assert code == 400, "invented decisions must be refused"
        code, body = call("POST", "/api/returns",
                          {"tracking": "EG99999", "courier": "Test D.", "office": "Delta Lines",
                           "reason": "DNR", "customer_phone": "01000000999", "day": "2026-10-24"}, token=tok)
        assert code == 201, body
        code, body = call("POST", "/api/returns",
                          {"tracking": "EG99999", "courier": "Test D.", "office": "Delta Lines",
                           "reason": "DNR", "customer_phone": "01000000999", "day": "2026-10-24"}, token=tok)
        assert code == 409, "same tracking twice must clash, not duplicate"
        with urllib.request.urlopen(BASE + "/") as r:
            assert r.status == 200
        print("RTS api tests passed")
    finally:
        srv.terminate()

if __name__ == "__main__":
    main()
