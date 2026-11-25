# MCP

Official Python SDK, `mcp>=2,<3` (PyPI listed 2.3.0 on 2026-11-24). In v2 the class is `MCPServer`, from `mcp.server`; the
v1 `FastMCP` import was removed. Sources disagree on the minimum Python (3.10 or 3.11); 3.12 satisfies both. STDIO is the
default for `run()`. stdout is the protocol, so all logging goes to stderr and a file, and nothing prints at import time.

**No MCP connection has been tested yet.** Feasibility below is from documentation, plus local `--help` for Claude Code.

## Tools

Read tools use `read_only_hint=True` (a hint to clients; the database guard is the enforcement).

| Tool | Available from |
|---|---|
| get_user_profile, search_memory, get_project_context, get_project_decisions, get_context_bundle, get_recent_activity | M2 |
| prepare_memory_proposal, prepare_project_update | M2 |
| get_conversation_summary | M3 |
| get_learning_progress, get_career_goals, prepare_learning_update | M4 |

A tool is registered only once its module works. Resources: profile, project overview, project architecture (M2);
learning progress, career goals (M4).

Limits: query 500 characters, 50 results, proposal content 4,000 characters, 20 pending proposals per client per hour,
response 32,000 characters. The last stays below Claude Code's documented default of 25,000 tokens.

## Sharing approval

A STDIO call cannot show a PAW dialog, and PAW may be closed. So:

1. In PAW the user previews the exact compiled bundle for a project and approves a **sharing grant**: project or global
   profile, categories, client, expiry (default 30 days).
2. Without a matching grant, tools return `sharing_not_approved` and say where to approve it. They return no data.
3. Items marked not shareable are never returned, whatever the grant.
4. Each response is logged in `share_log` and shown in the UI.

A grant approves a scope, so later items in that scope are shared without another prompt. The UI states this. The client
name comes from our own registration (`--client claude-code`); it is a label, not authentication.

The server matches `CLAUDE_PROJECT_DIR` or the working directory against registered projects. Returned text is wrapped as
reference data with provenance, because imported text may contain instructions.

## Provider feasibility

| | Claude Code | Codex | Google |
|---|---|---|---|
| On this machine | 2.1.331 | Not installed | Not installed |
| STDIO MCP | Yes | Yes | Yes (Antigravity CLI, `agy`) |
| Register via | `claude mcp add -s user paw -- ...` | `codex mcp add paw -- ...` | Edit `~/.gemini/config/mcp_config.json`; no add command documented |
| Auth status | `claude auth status` (exit 0 seen here) | `codex login status` (0 when logged in) | None documented: show "Unknown" |
| Subscription sign-in | Yes | ChatGPT sign-in | Gemini CLI: ended for personal accounts |
| Plan | M3 first | M3 second | Decision required |

Claude's status output is JSON that may contain account details. PAW keeps only the logged-in boolean. Logged-out
behaviour of both commands is untested.

Registration uses **user scope**, so PAW writes nothing into repositories. PAW shows the exact command and current entry,
asks first, backs up any file it edits, and offers removal.

### Claude Code

Anthropic's terms bar third parties from offering Claude login, routing requests through subscription credentials, or
handling credentials. They allow a user to sign in to the **unmodified** binary. They do not address a desktop app opening
it in a terminal. Our conservative reading: launch the user's own unmodified binary interactively; never bundle it, type
prompts into it, parse its output, use headless mode, or touch its tokens. Distributing PAW to others would need a fresh
review, and Claude may not appear in the product name or logo.

### Google (needs a decision)

- Google stopped serving Gemini CLI to free, AI Pro and Ultra accounts on 2026-06-18. Paid API keys and Code Assist
  Standard/Enterprise still work; Google's pages mention a separate schedule for those.
- The replacement is Antigravity CLI. Its additional terms say that using third-party software to access the service is a
  breach and may lead to suspension. The example given is OAuth reuse. Whether a plain launcher counts is unclear.

| Option | Effect |
|---|---|
| **G1 (recommended)** | PAW does not launch or configure `agy`. It shows an MCP snippet the user may add, and the user starts `agy` themselves |
| G2 | Full `AntigravityAdapter`; accepts account-suspension risk |
| G3 | `GeminiCLIAdapter` for API-key or enterprise users; conflicts with the no-API-key principle |
| G4 | Drop Google from v0.1 except conversation import |

G1 lowers the risk but does not settle the terms question, since the snippet still connects PAW to `agy`. MCP servers are
a documented `agy` feature.

## Sources (read 2026-11-24)

- [Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance), [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp), [Codex commands](https://learn.chatgpt.com/docs/developer-commands), [Codex auth](https://learn.chatgpt.com/docs/auth)
- [Gemini CLI transition](https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/), [consumer deprecation](https://developers.google.com/gemini-code-assist/docs/deprecations/code-assist-individuals)
- [Antigravity MCP](https://antigravity.google/docs/mcp), [Antigravity terms](https://antigravity.google/terms)
- [MCP SDK v2](https://py.sdk.modelcontextprotocol.io/v2/), [running](https://py.sdk.modelcontextprotocol.io/run/), [tools](https://py.sdk.modelcontextprotocol.io/servers/tools/), [testing](https://py.sdk.modelcontextprotocol.io/get-started/testing/), [PyPI](https://pypi.org/project/mcp/)

Long Claude Code and Codex pages were partly read through summaries. Recheck exact wording before implementing M3.
