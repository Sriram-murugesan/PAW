# Development

## Environment found (2026-11-24)

| Item | Found | Needed |
|---|---|---|
| OS | Ubuntu 24.04.3, XFCE, X11, x86_64, glibc 2.39 | OK |
| Hardware | 8 threads, 7 GB RAM (1.8 GB available at the time), 4 GB swap, 202 GB free disk | RAM is tight for Rust builds |
| Python | 3.12.3; no pip, no ensurepip | OK with uv |
| SQLite | 3.45.1 with FTS5 (Python); no `sqlite3` command | OK; command optional |
| Git | 2.43.0 | OK |
| gcc, g++, make, curl, wget | Present | OK |
| pkg-config | Missing; 1.8.1 installed since | OK |
| uv | Missing; 0.13.9 installed since, in `~/.local/bin` | OK |
| Node.js, npm | Missing; 24.22.3 and 11.19.1 installed since, through snap | OK |
| Rust, Cargo | Missing; 1.100.0 stable installed since, through apt's rustup | OK |
| Tauri libraries | Missing; installed since, webkit2gtk-4.1 is 2.52.6 | OK |
| Terminals | xfce4-terminal (default), xterm | OK |
| Claude Code | 2.1.331 | OK |
| Codex, Gemini CLI, Antigravity CLI | Not found on PATH | Not needed before M3 |
| Project directory | Empty | OK |

The install added 117 packages and upgraded 66, including Mesa, OpenSSL, GLib and WebKitGTK (2.48.3 to 2.52.6). None were
removed.

## Setup on a new machine (done on this one, 2026-11-24)

System packages, needing sudo. The list is Tauri's documented Debian set plus `pkg-config` and `rustup`:

```bash
sudo apt update && sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev pkg-config rustup
```

```bash
rustup default stable
```

uv, using its official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Node.js from the OpenJS Foundation snap (needs sudo):

```bash
sudo snap install node --classic --channel=24
```

Check:

```bash
node --version; npm --version; cargo --version; uv --version; pkg-config --modversion webkit2gtk-4.1
```

With this much RAM, use `CARGO_BUILD_JOBS=2` and close heavy applications during the first Rust build.

## All checks

From the repository folder; the second one opens PAW windows for about 15 seconds, on throwaway data:

```bash
scripts/check.sh
```

```bash
npm --prefix desktop run app:smoke
```

Last run 2026-11-24, all passing: 89 backend, 17 Rust and 24 interface tests; formatting, linting and types; the real-window
checks (acceptance, refusals, killed app, killed backend). Not covered: the native file dialogs, and any machine but this.

To work on the interface in a browser with a real backend and throwaway data: `npm --prefix desktop run dev:browser`.
The `smoke` Cargo feature adds a test hook; `app:smoke` rebuilds without it at the end.

## Backend checks

From `backend/`:

```bash
uv sync && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest -q
```

Tests use temporary
directories and never touch `~/.local/share/paw`. Warnings are errors, with one exemption: Starlette deprecates HTTPX in
its test client in favour of `httpx2`; we keep HTTPX as specified.

## Check policy

`ruff`, `mypy --strict`, `pytest` (real SQLite files, not in-memory, because WAL and multi-process behaviour matter);
`tsc`, `eslint`, `vitest`; `cargo fmt`, `cargo clippy`, `cargo test`. MCP tests use the SDK's in-memory `Client(server)`
and a real STDIO subprocess. The real
WebView is driven by `desktop/smoke`, which needs no extra packages, instead of Playwright or `tauri-driver`.

## Rules

Ask before deleting user files, changing provider configuration, changing Git history, installing with elevated
privileges, or reading outside registered paths. Never report a check as passing unless it ran.
