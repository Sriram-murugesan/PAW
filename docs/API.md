# REST API

Milestone 1 routes are implemented. Later milestones are planned.

Base `http://127.0.0.1:<random>`. Every route except `/health` needs `Authorization: Bearer`. Only the Rust proxy calls it.
OpenAPI, generated offline, is the source for TypeScript types (`npm run types`; the check fails if they are stale).

Single: `{"data": {...}}`. List: `{"data": [...], "next_cursor": null}`. Error:
`{"error": {"code": "version_conflict", "message": "...", "details": {}}}`.
Statuses: 200, 201, 204, 401, 403 (Host or Origin), 404, 409 (conflict), 411, 413, 422 (validation), 503 (restoring).
Validation errors name the field and never echo the input. No schema or docs routes are served.
Updates carry `version`; a mismatch returns 409.

`*` marks additions to the specification.

| Milestone | Routes |
|---|---|
| 1 | GET /health*, GET /api/dashboard, GET/PUT /api/profile |
| 1 | GET/POST /api/memory, GET*/PUT/DELETE /api/memory/{id}, POST /api/memory/{id}/archive*, POST .../unarchive*, GET /api/memory/{id}/history*, GET /api/memory/export* |
| 1 | GET/POST /api/memory/proposals, POST .../import*, POST .../{id}/approve, POST .../{id}/reject |
| 1 | GET /api/activity, GET/PUT /api/settings*, GET/POST /api/backups*, POST /api/backups/{id}/restore* |
| 2 | GET /api/memory/search |
| 2 | GET/POST /api/projects, GET/PUT/DELETE* /api/projects/{id}, GET .../context, GET .../activity, POST .../scan*, GET/POST .../decisions*, GET/PUT .../documents*, CRUD .../tasks* |
| 2 | POST /api/context/preview*, GET/POST/DELETE /api/sharing/grants*, GET /api/sharing/log* |
| 3 | GET /api/providers*, POST /api/providers/{id}/mcp* |
| 3 | GET /api/conversations, POST /api/conversations/import, GET /api/conversations/{id} |
| 4 | GET/POST /api/learning/skills, PUT* .../{id}, POST /api/learning/sessions, GET /api/learning/progress |
| 4 | GET/POST /api/career/goals, PUT* .../{id}; GET/POST /api/daily* |
| 4 | GET /api/git/activity, GET /api/git/projects/{id} |

Until M2, memory lists filter by category, status and plain substring. Literal paths such as `/search`, `/proposals` and
`/export` are declared before `/{id}`, which is UUID-typed.

Proposals keep the specification's `/api/memory/proposals` path although they now cover project and learning targets,
with a `target_type` filter.
