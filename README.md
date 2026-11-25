# PAW: Personal AI Workspace

A local-first desktop app that owns your personal context (memory, projects, learning, career) and supplies
the relevant parts to independent AI tools over MCP. It is not a chatbot and needs no LLM API key.

**Status: Milestone 1, all but packaging.** The desktop app works as a development build: memories, proposals, profile,
backups, export and import. It cannot be installed yet, and it connects to no AI tool yet (Milestones 2 and 3).

Build and start it, from this folder:

```bash
npm --prefix desktop run app:build && desktop/src-tauri/target/debug/paw-desktop
```

To load your profile for review: Settings, Import from file, `seed/initial-memories.json`. That file is kept out of Git
because it is personal.

| Document | Purpose |
|---|---|
| [PRD](docs/PRD.md) | Requirements with IDs, and where the plan departs from the original spec |
| [Architecture](docs/ARCHITECTURE.md) | Processes, boundaries, decisions, repository layout |
| [Database](docs/DATABASE.md) | Schema, search, migrations, backup |
| [MCP](docs/MCP.md) | Tools, sharing approval, provider feasibility |
| [Security](docs/SECURITY.md) | Trust boundaries, risks, controls, limits |
| [API](docs/API.md) | REST contract |
| [Roadmap](docs/ROADMAP.md) | Milestones, tasks, acceptance tests |
| [Development](docs/DEVELOPMENT.md) | Environment findings, setup, checks |
