import type { components } from "@/types/api";
import { invoke } from "./transport";

type Schemas = components["schemas"];
export type Memory = Schemas["MemoryOut"];
export type MemoryDetail = Schemas["MemoryDetail"];
export type MemoryInput = Schemas["MemoryCreate"];
export type MemoryChanges = Schemas["MemoryChanges"];
export type Category = Schemas["MemoryCategory"];
export type Proposal = Schemas["ProposalOut"];
export type Revision = Schemas["RevisionOut"];
export type Source = Schemas["SourceOut"];
export type Profile = Schemas["ProfileOut"];
export type Settings = Schemas["Settings"];
export type Dashboard = Schemas["DashboardOut"];
export type Activity = Schemas["ActivityOut"];
export type Backup = Schemas["BackupOut"];

export interface Page<T> {
  data: T[];
  next_cursor?: string | null;
}

export type FileOutcome =
  | { result: "cancelled" }
  | { result: "done"; count: number; skipped: number }
  | { result: "failed"; message: string };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

interface RawResponse {
  status: number;
  body: { error?: { code: string; message: string; details: Record<string, unknown> } } | null;
}

async function request<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  options: { query?: Record<string, string | undefined>; body?: unknown } = {},
): Promise<T> {
  const query = Object.fromEntries(
    Object.entries(options.query ?? {}).filter((entry): entry is [string, string] => !!entry[1]),
  );
  let response: RawResponse;
  try {
    const args = { method, path, query, body: options.body ?? null };
    response = await invoke<RawResponse>("api_request", args);
  } catch (error) {
    const code = typeof error === "string" ? error : "unavailable";
    const message =
      code === "too_large" ? "That is too large to save." : "PAW's background service did not answer.";
    throw new ApiError(0, code, message);
  }
  const { status, body } = response;
  if (status >= 200 && status < 300) return body as T;
  const error = body?.error;
  throw new ApiError(status, error?.code ?? "unknown", error?.message ?? "Something went wrong.", error?.details);
}

async function item<T>(...args: Parameters<typeof request>): Promise<T> {
  return (await request<{ data: T }>(...args)).data;
}

export interface MemoryFilter {
  status?: "CONFIRMED" | "ARCHIVED";
  category?: string;
  q?: string;
  cursor?: string;
}

export const api = {
  dashboard: () => item<Dashboard>("GET", "/api/dashboard"),

  memories: (filter: MemoryFilter) => request<Page<Memory>>("GET", "/api/memory", { query: { ...filter } }),
  memory: (id: string) => item<MemoryDetail>("GET", `/api/memory/${id}`),
  history: async (id: string) => (await request<Page<Revision>>("GET", `/api/memory/${id}/history`)).data,
  createMemory: (body: MemoryInput) => item<MemoryDetail>("POST", "/api/memory", { body }),
  updateMemory: (id: string, body: MemoryInput & { version: number }) =>
    item<MemoryDetail>("PUT", `/api/memory/${id}`, { body }),
  deleteMemory: (id: string) => request<null>("DELETE", `/api/memory/${id}`),
  setArchived: (id: string, archived: boolean) =>
    item<MemoryDetail>("POST", `/api/memory/${id}/${archived ? "archive" : "unarchive"}`),

  proposals: (cursor?: string) =>
    request<Page<Proposal>>("GET", "/api/memory/proposals", { query: { status: "PENDING", cursor } }),
  approve: (id: string, body: { edits?: MemoryChanges; current_version?: number }) =>
    item<MemoryDetail>("POST", `/api/memory/proposals/${id}/approve`, { body }),
  reject: (id: string) => item<Proposal>("POST", `/api/memory/proposals/${id}/reject`),

  profile: () => item<Profile>("GET", "/api/profile"),
  saveProfile: (body: Pick<Profile, "display_name" | "version"> & { profile_data: ProfileData }) =>
    item<Profile>("PUT", "/api/profile", { body }),
  settings: () => item<Settings>("GET", "/api/settings"),
  saveSettings: (body: Settings) => item<Settings>("PUT", "/api/settings", { body }),

  backups: async () => (await request<Page<Backup>>("GET", "/api/backups")).data,
  createBackup: () => item<Backup>("POST", "/api/backups"),
  restoreBackup: (id: string) => item<{ safety_backup: string }>("POST", `/api/backups/${id}/restore`),

  exportMemories: (format: "json" | "markdown") => invoke<FileOutcome>("export_memories", { format }),
  importMemories: () => invoke<FileOutcome>("import_memories"),
};

export type ProfileData = Record<string, string | string[]>;

export function messageOf(error: unknown): string {
  if (error instanceof ApiError) {
    const fields = error.details["fields"] as { field: string; message: string }[] | undefined;
    const first = fields?.[0];
    return first ? `${first.field.replace(/^body\./, "")}: ${first.message}` : error.message;
  }
  return "Something went wrong.";
}
