# Roadmap

A milestone closes only when its acceptance test, linting and type checks have been run and pass, and the docs match.

## Milestone 1: Desktop and memory foundation (in progress)

| # | Task | Done when | Status |
|---|---|---|---|
| 1.0 | Toolchain installed | Every version check in DEVELOPMENT.md passes | **Done** |
| 1.1 | Spike: Rust spawns a minimal FastAPI, proxies one call, kills cleanly | No orphan after `kill -9` of the desktop | **Done** |
| 1.2 | Spike: PyInstaller onedir inside a `.deb` | Frozen backend answers `/health`; startup time recorded | Not started; the only task left |
| 1.3 | uv workspace, ruff, mypy, pytest, Vite, Vitest, clippy, one check command | Passes on an empty project | **Done** (`scripts/check.sh`) |
| 1.4 | Database setup, M1 models, first migration, backup and restore | Migration up/down and restore tests | **Done** |
| 1.5 | Profile, memory, proposal, activity services | Approval, conflict, dedupe and history tests | **Done** |
| 1.6 | REST API with authentication and errors | API and authentication tests | **Done** |
| 1.7 | Desktop: supervision, proxy, error screen | Lifecycle tests | **Done** |
| 1.8 | UI: shell, Dashboard, Memory, Profile, Settings | Component tests; only working controls shown | **Done** |
| 1.9 | Seed import as proposals, export, docs | Acceptance test | **Done**; native file dialogs not exercised |

The acceptance test passes in the real desktop window (create, close, reopen, read; approve a proposal; restore a backup),
using a development build. Milestone 1 stays open until 1.2, because PAW cannot be installed yet.

Sidebar entries appear when their module works, so no page is a placeholder.

**Acceptance:** create a memory, close PAW, reopen, retrieve it. Also: approve a proposal, then restore a backup.

## Milestone 2: Project context and MCP

Registration and scanner; project documents and decisions; FTS; context engine and preview; grants and share log; MCP
server. **Acceptance:** the specification's 12-step end-to-end test with a test MCP client and no LLM subscription, plus a
manual check with Claude Code.

## Milestone 3: AI agent integration

Adapter interface; Claude Code; embedded PTY; external terminals; Codex; Google per decision; conversation import.
**Acceptance:** launch an authenticated CLI from PAW and read project context through MCP.

## Milestone 4: Monitoring and intelligence

Git; learning; career; productivity; timeline; dashboard analytics. Conversation summaries are written by the user or
submitted through MCP as proposals, because PAW has no model of its own. Semantic retrieval only if FTS proves inadequate.
**Acceptance:** dashboard shows reliable, persistent views from stored data.

## Decisions

| # | Question | Status |
|---|---|---|
| Q1 | Google provider (MCP.md G1-G4) | Open, recommend G1; needed by M3 |
| Q2 | Sharing grants instead of a prompt on each call | **Approved 2026-11-24** |
| Q3 | Schema changes V3-V6 in PRD.md | **Approved 2026-11-24** |
| Q4 | `.deb` only for v0.1, targeting Ubuntu 24.04+ | Open, recommend accept; needed by task 1.2 |
