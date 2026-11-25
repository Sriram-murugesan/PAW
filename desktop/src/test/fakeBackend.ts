import type { BackendStatus } from "@/services/backend";

export interface Call {
  method: string;
  path: string;
  query: Record<string, string>;
  body: unknown;
}

type Reply = { status: number; body: unknown } | ((call: Call) => { status: number; body: unknown });

/** Stands in for the Rust side. An unexpected request fails the test instead of returning nothing. */
export class FakeBackend {
  calls: Call[] = [];
  commands: string[] = [];
  status: BackendStatus = { state: "ready" };
  outcomes: Record<string, unknown> = {};
  private replies = new Map<string, Reply>();
  private listeners = new Set<(status: BackendStatus) => void>();

  on(method: string, path: string, body: unknown, status = 200) {
    this.replies.set(`${method} ${path}`, { status, body });
    return this;
  }

  handle(method: string, path: string, reply: (call: Call) => { status: number; body: unknown }) {
    this.replies.set(`${method} ${path}`, reply);
    return this;
  }

  emit(status: BackendStatus) {
    this.status = status;
    for (const listener of this.listeners) listener(status);
  }

  sent(method: string, path: string) {
    return this.calls.filter((c) => c.method === method && c.path === path);
  }

  invoke = (cmd: string, args?: Record<string, unknown>): Promise<unknown> => {
    this.commands.push(cmd);
    if (cmd === "backend_status") return Promise.resolve(this.status);
    if (cmd === "backend_retry") return Promise.resolve(null);
    if (cmd !== "api_request") return Promise.resolve(this.outcomes[cmd]);
    const call = args as unknown as Call;
    this.calls.push(call);
    const reply = this.replies.get(`${call.method} ${call.path}`);
    if (!reply) return Promise.reject(new Error(`unexpected ${call.method} ${call.path}`));
    return Promise.resolve(typeof reply === "function" ? reply(call) : reply);
  };

  onEvent = (_name: string, handler: (status: BackendStatus) => void) => {
    this.listeners.add(handler);
    return Promise.resolve(() => this.listeners.delete(handler));
  };
}

const at = "2026-11-24T10:00:00Z";

export const memory = (extra: object = {}) => ({
  id: "m1",
  category: "technical_skill",
  title: "FastAPI",
  content: "Uses FastAPI",
  confidence: 1,
  status: "CONFIRMED",
  shareable: true,
  version: 1,
  created_at: at,
  updated_at: at,
  sources: [{ id: "s1", source_type: "manual", source_id: null, reference_metadata: {}, created_at: at }],
  ...extra,
});

export const proposal = (extra: object = {}) => ({
  id: "p1",
  target_type: "MEMORY",
  operation: "CREATE",
  target_id: null,
  base_version: null,
  payload: { category: "achievement", title: "Shipped", content: "Shipped the bot" },
  confidence: 0.5,
  status: "PENDING",
  submitted_by: "file import",
  created_at: at,
  reviewed_at: null,
  sources: [{ id: "s2", source_type: "seed", source_id: null, reference_metadata: {}, created_at: at }],
  possible_duplicates: [],
  ...extra,
});

export const page = (...data: unknown[]) => ({ data, next_cursor: null });
export const problem = (code: string, message: string, details: object = {}) => ({
  error: { code, message, details },
});

export function standard() {
  return new FakeBackend()
    .on("GET", "/api/dashboard", {
      data: {
        confirmed_memories: 1,
        archived_memories: 0,
        pending_proposals: 1,
        memories_by_category: { technical_skill: 1 },
        latest_proposals: [proposal()],
        recent_activity: [
          { id: "e", event_type: "memory.created", project_id: null, entity_id: "m1", event_metadata: {}, occurred_at: at },
        ],
      },
    })
    .on("GET", "/api/settings", { data: { theme: "dark" } })
    .on("GET", "/api/memory", page(memory()))
    .on("GET", "/api/memory/m1", { data: memory() })
    .on("GET", "/api/memory/m1/history", page())
    .on("GET", "/api/memory/proposals", page(proposal()))
    .on("GET", "/api/profile", {
      data: { display_name: "A", profile_data: { Goals: ["One", "Two"], About: "Text" }, version: 3, updated_at: at },
    })
    .on("GET", "/api/backups", page({ id: "b1", reason: "manual", created_at: at, size_bytes: 98304 }));
}
