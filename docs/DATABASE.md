# Database

SQLite at `~/.local/share/paw/database/paw.db` (honours `XDG_DATA_HOME`). Directory mode 0700, files 0600. SQLite is
authoritative; Markdown and JSON files are exports.

## Conventions

UUIDv4 text primary keys. UTC ISO-8601 timestamps. Enumerations as text with CHECK constraints. On every connection:
`journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=10000`, `synchronous=NORMAL`,
`secure_delete=ON`. Writes use `BEGIN IMMEDIATE` and stay
short.

## Tables

| Table | Key columns and rules | Milestone |
|---|---|---|
| profile | One row; `profile_data` JSON validated by Pydantic | 1 |
| memories | category, title, content, confidence, status `CONFIRMED/ARCHIVED`, `version`, `shareable` | 1 |
| memory_revisions | memory_id, version, snapshot, change_reason, proposal_id; append-only | 1 |
| proposals | target_type `MEMORY/PROJECT/DECISION/LEARNING`, operation, target_id, base_version, payload, status `PENDING/APPROVED/REJECTED/SUPERSEDED`, submitted_by, reviewed_at | 1 |
| memory_sources | exactly one of memory_id and proposal_id, source_type, source_id, reference_metadata | 1 |
| activity_events | event_type, project_id, entity_id, event_metadata, occurred_at | 1 |
| settings | key unique, JSON value | 1 |
| projects, project_paths | one primary path per project; canonical path unique | 2 |
| project_documents | overview/architecture/known issues, versioned | 2 |
| project_decisions | status `ACTIVE/SUPERSEDED`, supersedes_id | 2 |
| tasks, milestones | project_id nullable so daily tasks share the table | 2 |
| search_documents, search_fts | derived index; see below | 2 |
| sharing_grants | scope, project_id, categories, client, expires_at, revoked_at | 2 |
| share_log | client, tool, grant_id, source ids, byte count, occurred_at; **no content** | 2 |
| agent_sessions | provider, project, mode, started, ended, exit code; **no transcript** | 3 |
| conversations, messages | provider, external_id, content hash unique for repeat imports | 3 |
| skills, skill_topics, skill_resources, learning_sessions | topic state: pending/completed/weak | 4 |
| career_goals, goal_skills, career_milestones | | 4 |
| git_events | unique(project_id, commit_hash); `branch` = branch observed at scan time, since Git does not record a commit's branch | 4 |
| daily_reviews | one per local date | 4 |

Deleting a project removes its derived data only, never files on disk. Deleting a memory also removes its revisions,
sources, search rows, and every proposal that created or targets it. `secure_delete` overwrites freed pages, and a test
checks that the text is gone from the database file. **Older backups still contain it**; the UI must say so.

## Approval rules

- Approval is one transaction: check `PENDING`, check `base_version` equals the current version, apply, write a revision
  and a source, mark approved. A version mismatch returns 409 and shows both versions.
- Triggers reject inserting a proposal in any state other than `PENDING`, changing a proposal's content, deciding it
  twice, and updating a revision. Corrections made while approving go into the memory, not the proposal.
- To approve over a newer memory, the user confirms its current version. The replaced text stays in history.
- Deduplication uses a normalized exact hash (FTS similarity follows in M2). It only flags a possible duplicate.

## Search

One FTS5 index over `search_documents(seq INTEGER PRIMARY KEY, entity_type, entity_id, title, body)`:

- Entities keep UUID keys. FTS external content needs a stable integer, which SQLite guarantees only for an explicit
  INTEGER PRIMARY KEY. A small VACUUM test did not reproduce renumbering of implicit rowids, but we do not rely on it.
- Alembic batch migrations recreate tables, which drops their triggers. Only `search_documents` has FTS triggers, and it is
  never batch-migrated. Services update it in the same transaction, and a rebuild command restores it.
- User text is never passed to `MATCH` unquoted: `c++`, `user's` and a trailing `AND` all raise syntax errors (tested).
  Each term is double-quoted with quotes doubled.

## MCP connection guard

`paw_mcp` connects with a SQLite authorizer allowing reads plus INSERT into `proposals`, `memory_sources`, `share_log`.
It guards against defects in our code, not against other programs running as the same user.

## Migrations, backup, restore

Only the backend migrates, after an automatic backup. Backups use SQLite's online backup API, never a file copy, since
recent data may still be in the WAL. Restore: verify integrity, foreign keys and schema version, pause
requests, take a safety backup, copy the content in through the backup API (safe with other open processes, no file
swap), migrate if older. Any failure puts the safety backup back. Backups from a newer schema are refused.

## Planning probes (Python 3.12.3, SQLite 3.45.1, 2026-11-24)

| Check | Result |
|---|---|
| FTS5 available | Yes |
| 3 processes x 500 WAL transactions | 1,500 rows, no lock errors |
| Authorizer: FTS search and proposal insert allowed | Yes |
| Authorizer: memory insert/update, proposal update/delete, ATTACH, DROP, PRAGMA write | All denied |
| Online backup with an open writer | integrity ok, newest row present |

These ran against throwaway tables, not this schema. The M1 subset now exists as tests in
`backend/tests`; FTS and the MCP authorizer remain for M2.
