import os
import sys
import time
import socket
import shutil
import logging
import subprocess
import threading
from flask import Flask, jsonify, send_from_directory
from pythonjsonlogger import jsonlogger

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
app = Flask(__name__)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logger = logging.getLogger("slsa-hardened-app")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

STARTED = time.time()
POD = socket.gethostname()
IMAGE_REF = os.environ.get("IMAGE_REF", "unknown")
served = {"n": 0}
lock = threading.Lock()


@app.after_request
def add_headers(resp):
    # Close each connection so the Kubernetes Service balances every request across pods
    resp.headers["Connection"] = "close"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/health")
def health_check():
    logger.info("Health check endpoint invoked", extra={"status": "healthy", "pod": POD})
    return jsonify({"status": "UP", "framework": "Flask", "pod": POD}), 200


@app.get("/api/whoami")
def whoami():
    with lock:
        served["n"] += 1
        n = served["n"]
    return jsonify(
        pod=POD, uid=os.getuid(), gid=os.getgid(), pid=os.getpid(),
        boot=int(STARTED * 1000), uptime=round(time.time() - STARTED, 1),
        served=n, image=IMAGE_REF,
    )


def proc_status():
    keys = ("Uid", "Gid", "CapEff", "CapPrm", "CapBnd", "NoNewPrivs", "Seccomp")
    out = {}
    with open("/proc/self/status") as f:
        for line in f:
            k, _, v = line.partition(":")
            if k in keys:
                out[k] = v.strip()
    return out


def atk_shell():
    attempt = "execute /bin/sh, bash, dash with: -c id"
    paths = ["/bin/sh", "/bin/bash", "/bin/dash", "/bin/rbash",
             "/usr/bin/sh", "/usr/bin/bash", "/usr/bin/dash", "/usr/bin/rbash"]
    for p in paths:
        if os.path.exists(p):
            try:
                r = subprocess.run([p, "-c", "id"], capture_output=True, timeout=3)
                return False, attempt, f"{p} ran and returned: {r.stdout.decode().strip()}"
            except OSError:
                pass
    return True, attempt, f"{len(paths)} shell paths tried, none could be executed"


def atk_tools():
    attempt = "locate curl and wget on PATH"
    found = [t for t in ("curl", "wget") if shutil.which(t)]
    if found:
        return False, attempt, "found: " + ", ".join(found)
    return True, attempt, "neither curl nor wget exists in this image"


def atk_write():
    attempt = "create files in /etc, /app and /tmp"
    results, wrote = [], False
    for d in ("/etc", "/app", "/tmp"):
        path = os.path.join(d, "pwned.txt")
        try:
            with open(path, "w") as f:
                f.write("x")
            os.remove(path)
            wrote = True
            results.append(f"{d}: WRITE SUCCEEDED")
        except OSError as e:
            results.append(f"{d}: {e.strerror} (errno {e.errno})")
    return (not wrote), attempt, "; ".join(results)


def atk_privesc():
    attempt = "os.setuid(0) and read /etc/shadow"
    results, escalated = [], False
    try:
        os.setuid(0)
        escalated = True
        results.append("setuid(0) SUCCEEDED")
    except OSError as e:
        results.append(f"setuid(0): {e.strerror}")
    try:
        with open("/etc/shadow") as f:
            f.read(1)
        escalated = True
        results.append("/etc/shadow READABLE")
    except OSError as e:
        results.append(f"/etc/shadow: {e.strerror}")
    return (not escalated), attempt, "; ".join(results)


def atk_identity():
    attempt = "read /proc/self/status (uid, capabilities, no_new_privs)"
    s = proc_status()
    uid = s.get("Uid", "?").split()[0] if s.get("Uid") else "?"
    caps_empty = set(s.get("CapEff", "x")) <= {"0"}
    nnp = s.get("NoNewPrivs") == "1"
    detail = (f"uid={uid}, CapEff={s.get('CapEff')}, CapBnd={s.get('CapBnd')}, "
              f"NoNewPrivs={s.get('NoNewPrivs')}, Seccomp={s.get('Seccomp')}")
    return (uid not in ("0", "?") and caps_empty and nnp), attempt, detail


ATTACKS = {
    "shell": ("Spawn a shell", atk_shell),
    "tools": ("Find download tools", atk_tools),
    "write": ("Write to the filesystem", atk_write),
    "privesc": ("Escalate to root", atk_privesc),
    "identity": ("Inspect own privileges", atk_identity),
}


@app.post("/api/attack/<name>")
def attack(name):
    if name not in ATTACKS:
        return jsonify(error="unknown attack"), 404
    title, fn = ATTACKS[name]
    try:
        blocked, attempt, detail = fn()
    except Exception as e:  # report honestly instead of hiding failures
        blocked, attempt, detail = False, "test crashed", f"{type(e).__name__}: {e}"
    logger.warning("attack simulation", extra={"attack": name, "blocked": blocked, "pod": POD})
    return jsonify(name=name, title=title, pod=POD, attempt=attempt, blocked=blocked, detail=detail)


@app.post("/api/chaos/crash")
def crash():
    logger.error("chaos: crash requested, exiting process", extra={"pod": POD})
    threading.Timer(0.5, lambda: os._exit(1)).start()
    return jsonify(pod=POD, crashing=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)