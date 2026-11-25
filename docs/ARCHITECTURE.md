# Architecture

Verdict: Tauri 2 + React + FastAPI + SQLite is feasible on this machine. The costs are a Python runtime to bundle and
supervise, and two processes sharing one database. Both have a plan below.

## Processes

```
 Tauri (Rust) ---IPC--- WebView (React)
   |  |  |
   |  |  +-- PTY (portable-pty) ---- claude / codex            [M3]
   |  +----- external terminal (argv launch)                   [M3]
   +-------- HTTP 127.0.0.1:<random> + bearer --> FastAPI --+
                                                            |  paw.services  --> SQLite (WAL)
 claude / codex ---STDIO---> paw_mcp -----------------------+  (guarded connection)
```

| Process | Started by | Owns | Must not |
|---|---|---|---|
| Desktop (Rust) | User | Backend supervision, token, PTYs, dialogs | Contain domain logic or open the database |
| WebView | Desktop | Presentation | Hold the API token, spawn processes, reach the network |
| Backend | Desktop | Migrations, REST, monitors, all approvals | Bind beyond 127.0.0.1 |
| `paw_mcp` | The AI CLI | Tool schemas, output limits, audit | Migrate, approve, scan files, run commands, call HTTP |
| AI CLI | PAW or user | Its own login and reasoning | Be modified, driven or scraped by PAW |

## Service boundaries

`api` and `paw_mcp` are thin adapters. Both call `paw.services` and `paw.context_engine`, which use `paw.models` through a
session passed in by the caller. Dependencies point one way:
`api | paw_mcp -> context_engine -> services -> schemas -> models -> db -> core`. An import-linter check enforces this.

## Backend lifecycle

1. Rust takes a single-instance lock, generates a 256-bit token, and spawns the backend with piped stdin and stdout.
2. The token goes over **stdin**, not arguments or environment, so child processes and process listings do not see it.
3. The backend migrates, binds `127.0.0.1:0`, and prints one JSON line with its port. Rust then polls `/health`.
4. The backend exits when stdin reaches EOF, so a crashed desktop leaves no orphan. Rust sends SIGTERM, then SIGKILL.
5. On unexpected exit: restart up to 3 times with backoff, then show an error screen with the log location.

Steps 2 to 4 are implemented and tested on the backend side. Measured startup is 2.1 s and 81 MB, unfrozen, on this
machine. Exit codes: 3 already running, 4 bad token, 5 database. Errors are one JSON line on stdout.

The MCP server starts independently. If the database is missing or its schema version differs, it returns a clear error
and never migrates.

## Context engine (v0.1)

Deterministic; no LLM is available to it. Intent = keyword rules. Project = explicit id, then working directory, then
name or alias match. Retrieval = structured queries plus FTS5/BM25. Rank = priority class from the spec, then BM25, then
recency. Budget = characters/4 token estimate, default 4,000 and maximum 8,000 tokens. Every item carries `source_ref` and
`reason`.
If no project resolves, the result is an explicit "ambiguous", never a guess.

## Decisions

| ID | Decision | Why |
|---|---|---|
| A1 | WebView calls a Rust `api_request` command, which forwards to FastAPI | Token stays out of JavaScript; no CORS or mixed-content handling; CSP can block all network |
| A2 | Spawn the backend from Rust, with no shell plugin in the WebView | Smallest capability set |
| A3 | `spawn_session(provider_id, project_id)`; no executable or argument from the frontend | No arbitrary execution |
| A4 | One frozen Python build (PyInstaller **onedir**) with `serve` and `mcp` subcommands | One dependency set; onefile unpacks on every start and Codex allows 10 s for MCP startup |
| A5 | `.deb` is the v0.1 package | Stable path for MCP registration |
| A6 | Service layer is synchronous SQLAlchemy | Simple transactions; SQLite is local |
| A7 | No GitPython, Redis, vector database or Docker | Not needed for v0.1 |

A1, A2 and the lifecycle are implemented and tested. A4 is still unproven (task 1.2). A development build finds the backend
in the workspace environment by absolute path, so rebuild after moving the folder.

Interface decisions: native `<dialog>` instead of Radix, whose injected styles the policy would block; small components in
the shadcn style; TypeScript 5.9, because the linter and type generator do not support 7 yet; no router.

## Linux specifics

- GUI apps do not inherit the shell `PATH`, and CLIs commonly live in `~/.local/bin`. Resolve from a fixed list of
  directories plus a user-set absolute path, and show the resolved path.
- Terminal launch uses argument arrays: `xfce4-terminal --working-directory=DIR -x CMD ARGS` and `xterm -e CMD ARGS`
  (with the process cwd set). Never `xfce4-terminal -e`, which takes one command string. Both flags exist here; launching
  was not tested.
- glibc here is 2.39. A build made here targets Ubuntu 24.04 or newer; build on 22.04 to support older systems.
- inotify limit here is 57,268 watches. Watch registered roots with exclusions and fall back to polling.

## Repository layout

```
paw/
├── pyproject.toml              uv workspace: backend, mcp-server
├── backend/
│   ├── pyproject.toml  alembic.ini
│   ├── paw/
│   │   ├── main.py             serve entry point
│   │   ├── api/  core/  db/  models/  schemas/  services/
│   │   ├── context_engine/     intent, project_resolver, retriever, ranker, compiler, token_budget
│   │   ├── monitors/           git_monitor, file_monitor
│   │   └── integrations/       provider_registry and adapters
│   └── tests/
├── mcp-server/
│   ├── pyproject.toml
│   ├── paw_mcp/                server.py, guard.py, tools/
│   └── tests/
├── desktop/
│   ├── src/                    app, components, features, hooks, services, types
│   └── src-tauri/              src (backend, api_proxy, pty, terminal), capabilities, tauri.conf.json
├── packaging/                  PyInstaller spec, build scripts
└── docs/
```

Directories are created when they gain content.
