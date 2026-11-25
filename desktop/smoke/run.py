"""Runs the real desktop app against throwaway data. Build first; see docs/DEVELOPMENT.md.

Opens PAW windows on the current display. Never touches the user's own data.
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
APP = HERE.parent / "src-tauri" / "target" / "debug" / "paw-desktop"
failures = []


def check(name, good, detail=""):
    print(("  ok    " if good else "  FAIL  ") + name, "" if good else detail)
    if not good:
        failures.append(name)


def children(pid):
    listing = Path(f"/proc/{pid}/task/{pid}/children")
    found = []
    for task in Path(f"/proc/{pid}/task").glob("*/children"):
        found += [int(p) for p in task.read_text().split()]
    return found or ([int(p) for p in listing.read_text().split()] if listing.exists() else [])


def backend_of(pid):
    for child in children(pid):
        if b"paw-backend" in Path(f"/proc/{child}/cmdline").read_bytes():
            return child
    return None


def running(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[0] != "Z"
    except FileNotFoundError:
        return False


def gone(pid, seconds=10):
    end = time.monotonic() + seconds
    while running(pid) and time.monotonic() < end:
        time.sleep(0.05)
    return not running(pid)


class App:
    def __init__(self, home, script):
        source = home / f"{script}.js"
        # A function scope, because the same page may run it twice.
        source.write_text("(() => {" + (HERE / "lib.js").read_text() + (HERE / f"{script}.js").read_text() + "})();")
        env = {
            **os.environ,
            "XDG_DATA_HOME": str(home / "data"),
            "XDG_CACHE_HOME": str(home / "cache"),
            "PAW_SMOKE_SCRIPT": str(source),
        }
        self.started = time.monotonic()
        self.process = subprocess.Popen([APP], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        os.set_blocking(self.process.stdout.fileno(), True)

    def report(self):
        timer = __import__("threading").Timer(90, self.process.kill)
        timer.start()
        for line in self.process.stdout:
            if line.startswith("SMOKE "):
                timer.cancel()
                text = line[6:].strip()
                return json.loads(text) if text.startswith("{") else text
        timer.cancel()
        return {"ok": False, "error": "no report", "stderr": self.process.stderr.read()[-600:]}

    def finish(self):
        try:
            return self.process.wait(20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            return "did not exit"


def main():
    with tempfile.TemporaryDirectory(prefix="paw-smoke-") as directory:
        home = Path(directory)

        print("1. create a memory in the real window, and try what must be refused")
        app = App(home, "1-create")
        r = app.report()
        check("flow", r.get("ok"), r)
        if r.get("ok"):
            check("focus starts in Title", r["focus"])
            check("styles load under the security policy", r["styled"] == "rgb(14, 16, 21)", r["styled"])
            check("the app itself breaks no policy", r["appViolations"] == [], r["appViolations"])
            for name, outcome in r["security"].items():
                check(f"refused: {name}", outcome.startswith("refused"), outcome)
                if "-v" in sys.argv:
                    print("          ", outcome)
            if "-v" in sys.argv:
                print("          ", r["blocked"])
        backend = backend_of(app.process.pid)
        check("closing the window exits cleanly", (code := app.finish()) == 0, code)
        check("and stops the backend", backend is None or gone(backend))

        print("2. reopen: memory is there; approve a proposal; restore a backup")
        app = App(home, "2-reopen")
        r = app.report()
        check("flow", r.get("ok"), r)
        check("no policy violations", r.get("appViolations") == [], r.get("appViolations"))
        app.finish()

        print("3. kill the app outright, start it twice, terminate it")
        app = App(home, "3-idle")
        check("running", app.report().get("ok"))
        backend = backend_of(app.process.pid)
        check("backend found", backend is not None)
        app.process.send_signal(signal.SIGKILL)
        app.process.wait()
        check("backend exits after the app is killed", gone(backend))
        app = App(home, "3-idle")
        check("starts again after being killed", app.report().get("ok"))
        second = subprocess.run([APP], env={**os.environ, "XDG_DATA_HOME": str(home / "data")}, timeout=20, check=False)
        check("a second launch hands over and exits", second.returncode == 0 and app.process.poll() is None)
        backend = backend_of(app.process.pid)
        app.process.terminate()
        app.process.wait(15)
        check("backend exits after the app is terminated", gone(backend))

        print("4. the backend crashes while something is being typed")
        app = App(home, "4-crash")
        check("ready to crash", app.report() == "CRASH-NOW")
        os.kill(backend_of(app.process.pid), signal.SIGKILL)
        r = app.report()
        check("typed text survives and saves", r.get("ok") and r.get("kept") == "Typed before the crash", r)
        app.finish()

        logs = (home / "data" / "paw" / "logs" / "paw.log").read_text()
        check("log holds no content", not re.search("Kept through|Typed before|Saved after|AI/ML", logs))
    print("FAILED: " + ", ".join(failures) if failures else "all passed")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
