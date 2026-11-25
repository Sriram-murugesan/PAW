# Product requirements

Condensed from the PAW v0.1 master specification so that requirements can be traced to code and tests.
It does not replace the original; keep that alongside this repository.

## Principle

AI models may change. The user's context and history stay consistent, local, and under the user's control.

## Requirements

| ID | Requirement | Milestone |
|---|---|---|
| MEM-1 | Create, view, search, filter, edit, archive, delete and export memories in 12 categories | 1 (FTS search in 2) |
| MEM-2 | Extracted or agent-submitted information becomes a proposal; only the user makes it permanent | 1 |
| MEM-3 | Confirmed memories are never silently overwritten; history and source are visible | 1 |
| PRO-1 | Profile is fully editable; nothing about the user is hardcoded | 1 |
| PRJ-1 | Register a project directory with explicit permission; never scan elsewhere | 2 |
| PRJ-2 | Scan known file types, with exclusions for secrets, binaries, dependencies and VCS internals | 2 |
| PRJ-3 | Overview, architecture, decisions, tasks and milestones; detected changes are proposals | 2 |
| CTX-1 | Compile a ranked, size-limited context bundle with provenance and reasons | 2 |
| CTX-2 | Preview and approve what is shared before it leaves PAW | 2 |
| MCP-1 | 9 read tools, 3 proposal tools, resources; STDIO; shared domain services | 2 (tools for later modules in 4) |
| AI-1 | Detect, report, configure and launch official CLIs; never handle their credentials | 3 |
| TRM-1 | Embedded real PTY and external terminal launch | 3 |
| CNV-1 | Import ChatGPT, Claude, Gemini, Markdown, text and JSON conversations | 3 |
| GIT-1 | Read-only Git monitoring, timeline and charts | 4 |
| LRN-1 | Skills, sessions, weak areas; mastery is never set automatically | 4 |
| CAR-1 | Goals mapped to skills, gaps, milestones, certifications, interview prep | 4 |
| DAY-1 | Daily goals, tasks and end-of-day review; no invasive monitoring | 4 |
| SEC-1 | The 20 security and privacy requirements, tracked in SECURITY.md | all |
| OPS-1 | Backup, restore, export and deletion | 1 |

## Seed data

The user profile in section 3 of the specification is imported **as pending proposals**, from an editable file outside
application code. The user confirms each item, because historical details may be out of date.

## Departures from the specification

| # | Specification | Problem | Plan |
|---|---|---|---|
| V1 | Gemini CLI with Google sign-in | Ended for personal accounts on 2026-06-18 | See MCP.md; **needs your decision** |
| V2 | "Preview and Approval" before each MCP response | A STDIO tool call has no UI, and PAW may be closed | Sharing grants approved in advance; fails closed |
| V3 | `memories.status` holds INFERRED and REJECTED, and so does `memory_proposals.status` | Two sources of truth | Memories: CONFIRMED/ARCHIVED. INFERRED and REJECTED are proposal states |
| V4 | Only a memory proposal table | Project and learning proposals have nowhere to live | One `proposals` table with a target type |
| V5 | `projects.repository_path` and `project_paths` | Two sources of truth | `project_paths` with one primary path |
| V6 | Memory history and context provenance required, but no tables | Cannot be built | Add revision, grant and share-log tables |
| V7 | `activity_events.metadata` | `metadata` is reserved in SQLAlchemy declarative models | Attribute `event_metadata` |
| V8 | `mcp-server/server.py` importing the backend | Not importable across directories; `mcp` would shadow the SDK | uv workspace with package `paw_mcp` |
| V9 | GitPython where useful | Git CLI with hardened flags is easier to prove read-only | Git CLI only |
| V10 | Dashboard, profile, memory etc. endpoints only | No endpoints for tasks, providers, context, settings, backup | Added in API.md |
| V11 | "Tauri Linux bundles" | An AppImage mounts at a changing path, which breaks registered MCP commands | `.deb` first |
