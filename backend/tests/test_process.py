"""Runs the real backend process, as the desktop app will."""

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

TOKEN = "s" * 43
MEMORY = {"category": "technical_skill", "title": "Kept", "content": "canary-secret"}


class Backend:
    def __init__(self, home: Path, token: str = TOKEN) -> None:
        env = {**os.environ, "XDG_DATA_HOME": str(home)}
        self.process = subprocess.Popen(
            [sys.executable, "-m", "paw.main", "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(f"{token}\n".encode())
        self.process.stdin.flush()
        self.hello: dict[str, Any] = json.loads(self.process.stdout.readline() or "{}")

    def request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        url = f"http://127.0.0.1:{self.hello['port']}{path}"
        return httpx.request(method, url, headers=headers, trust_env=False, **kw)

    def close_stdin(self) -> int:
        assert self.process.stdin
        self.process.stdin.close()
        return self.process.wait(10)

    def cleanup(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(5)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream:
                stream.close()


@pytest.fixture
def start(tmp_path: Path) -> Iterator[Any]:
    running: list[Backend] = []

    def run(token: str = TOKEN) -> Backend:
        running.append(Backend(tmp_path, token))
        return running[-1]

    yield run
    for backend in running:
        backend.cleanup()


def test_memory_survives_restart(start: Any) -> None:
    first = start()
    assert first.hello["event"] == "ready"
    created = first.request("POST", "/api/memory", json=MEMORY).json()["data"]
    assert first.close_stdin() == 0
    second = start()
    data = second.request("GET", f"/api/memory/{created['id']}").json()["data"]
    assert data["content"] == MEMORY["content"]


def test_memory_survives_kill(start: Any) -> None:
    first = start()
    first.request("POST", "/api/memory", json=MEMORY)
    first.process.send_signal(signal.SIGKILL)
    first.process.wait(5)
    assert len(start().request("GET", "/api/memory").json()["data"]) == 1


def test_listens_on_loopback_only(start: Any) -> None:
    port = f"{start().hello['port']:04X}"
    rows = [r.split() for r in Path("/proc/net/tcp").read_text().splitlines()[1:]]
    listening = [r[1] for r in rows if r[3] == "0A" and r[1].endswith(f":{port}")]
    assert listening == [f"0100007F:{port}"]
    six = [r.split() for r in Path("/proc/net/tcp6").read_text().splitlines()[1:]]
    assert not [r for r in six if r[3] == "0A" and r[1].endswith(f":{port}")]


def test_token_is_not_visible_to_other_processes(start: Any) -> None:
    proc = Path(f"/proc/{start().process.pid}")
    assert TOKEN.encode() not in (proc / "cmdline").read_bytes() + (proc / "environ").read_bytes()


def test_second_backend_refuses_to_start(start: Any) -> None:
    first = start()
    second = start()
    assert second.hello == {"event": "error", "code": "already_running"}
    assert second.process.wait(5) == 3
    assert first.request("GET", "/health").status_code == 200


def test_short_token_is_refused(start: Any, tmp_path: Path) -> None:
    backend = start("short")
    assert backend.hello["code"] == "bad_token" and backend.process.wait(5) == 4
    assert not (tmp_path / "paw").exists()


def test_exits_when_parent_is_killed(tmp_path: Path) -> None:
    """The parent here plays the desktop app and dies without any chance to clean up."""
    script = (
        "import subprocess,sys,time\n"
        "p=subprocess.Popen([sys.executable,'-m','paw.main','serve'],"
        "stdin=subprocess.PIPE,stdout=subprocess.PIPE)\n"
        f"p.stdin.write(b'{TOKEN}\\n');p.stdin.flush()\n"
        "sys.stdout.buffer.write(p.stdout.readline());sys.stdout.flush()\n"
        "time.sleep(60)\n"
    )
    env = {**os.environ, "XDG_DATA_HOME": str(tmp_path)}
    with subprocess.Popen(
        [sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env
    ) as parent:
        assert parent.stdout
        pid = json.loads(parent.stdout.readline())["pid"]
        parent.kill()
        parent.wait(5)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            stat = Path(f"/proc/{pid}/stat")
            if not stat.exists() or stat.read_text().rpartition(")")[2].split()[0] == "Z":
                return
            time.sleep(0.05)
        os.kill(pid, signal.SIGKILL)
        pytest.fail("backend outlived its parent")


def test_log_file_is_private_and_clean(start: Any, tmp_path: Path) -> None:
    backend = start()
    backend.request("POST", "/api/memory", json=MEMORY)
    backend.request("GET", "/api/memory", params={"q": "canary-secret"})
    backend.close_stdin()
    log = tmp_path / "paw" / "logs" / "paw.log"
    text = log.read_text()
    assert log.stat().st_mode & 0o777 == 0o600
    assert '"path": "/api/memory"' in text
    assert "canary-secret" not in text and TOKEN not in text
    assert backend.process.stderr and b"canary-secret" not in backend.process.stderr.read()
