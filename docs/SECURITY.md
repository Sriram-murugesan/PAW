# Security

## Trust boundaries

| Input | Trust |
|---|---|
| User actions in the PAW UI | Trusted; the only source of approvals |
| WebView | Semi-trusted: no token, no filesystem, no process or network access |
| MCP clients and their arguments | Untrusted |
| Project files, Git data, imported conversations | Untrusted, including any instructions inside them |
| Other programs running as the same user | **Outside what PAW can defend against** |

## Known limits to state in the UI

1. **An AI CLI with shell access can read `paw.db` directly**, going around MCP, grants and approvals. File modes do not
   stop the same user. Where the CLI supports it, offer a deny rule for `~/.local/share/paw`. Encryption with a key from
   the system keyring can be evaluated later. MCP grants govern the intended path; they are not a sandbox.
2. Data sent to a provider leaves the computer and follows that provider's terms.
3. The database and backups are not encrypted in v0.1. Full-disk encryption is advised.

## Risks and controls

| Risk | Control | Test |
|---|---|---|
| Another local process calls the API | Random port, bearer token over stdin, constant-time compare, Host check, any Origin refused | Missing and wrong token on every route; foreign Host; Origin |
| XSS in displayed Markdown or imports | No raw HTML; strict CSP; token not in WebView | Payload fixtures |
| API proxy abuse | Method and path allowlist, body limit, fixed base URL | Absolute URL and `..` rejected |
| Agent poisons memory | PENDING-only trigger, SQLite authorizer, rate limit, human review showing raw text and submitter | Forged status, direct writes |
| Prompt injection through stored text | Reference-data wrapping, provenance, no tool that executes | Injection fixtures |
| Path traversal or symlink escape in scans | Resolve real path, require containment, do not follow symlinks, recheck on open | Symlink and `..` fixtures |
| Secrets captured by scanning | Name denylist, size limit, binary detection, pattern redaction, filename allowlist | `.env*`, keys, tokens in README |
| Malicious repository runs code through Git | Hardened Git, below | Repository with hostile fsmonitor/textconv |
| Argument injection at launch | argv arrays, absolute executables, provider and project ids only | Paths with spaces, quotes, leading `-` |
| Token leaks to AI CLIs | Token never in environment; PTY environment is an allowlist | Inspect child environment |
| Log disclosure | Structured logs with ids and counts; redaction filter; no bodies or PTY output | Canary secret grep |
| Import bombs | File, message and nesting limits; stream parsing | Oversized fixtures |

Redaction by pattern misses some secrets. Exclusion is the main control.

## Git is read-only

Allowed subcommands: `log`, `status`, `branch --list`, `rev-parse`, `for-each-ref`, `diff --name-only`. Always set
`GIT_OPTIONAL_LOCKS=0` (otherwise `status` may rewrite the index), `GIT_TERMINAL_PROMPT=0`, `--no-ext-diff`,
`--no-textconv`, `-c core.fsmonitor=false` and `-c core.hooksPath=/dev/null`, since repository configuration can name
programs to run. Use a timeout, and never change `safe.directory`.

## Specification requirements

| Spec items | Where | Milestone |
|---|---|---|
| 1-6, 20 | Architecture, provider adapters, Git rules | 1-4 |
| 7, 8, 18 | Backend lifecycle, API proxy, capabilities | 1 |
| 9, 10 | Scanner | 2 |
| 11, 12, 19 | MCP guard and schemas | 2 |
| 13, 14 | Grants, share log, proposals | 1-2 |
| 15, 16, 17 | Backup, export, deletion, logging | 1 |

## Implemented so far

Loopback binding, token over stdin, request guard, body limit, private file modes, approval triggers, full deletion,
content-free logs, backup and restore. All have tests. 21 deliberate breakages in a copy now each fail
a test; two first exposed weak tests, since strengthened. Not every control was broken this way.

Desktop: the window may only listen for backend status and call PAW's five commands. Checked in the real WebView, each
refused: dialog, window, webview, path and emit plugins; unknown commands; `/health`, `..` and PATCH through the proxy;
outside and loopback fetch; inline script; remote image; navigation. The backend gets six environment variables and no
others. The app itself triggers no policy violation. Everything else above is still planned.

One accepted exception: any program running as the same user can attach to or read these processes.
