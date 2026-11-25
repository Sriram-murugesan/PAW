import { invoke, onEvent } from "./transport";

export type BackendStatus =
  | { state: "starting" }
  | { state: "ready" }
  | { state: "failed"; code: string }
  | { state: "stopped" };

export const backend = {
  status: () => invoke<BackendStatus>("backend_status"),
  retry: () => invoke<void>("backend_retry"),
  onStatus: (handler: (status: BackendStatus) => void) => onEvent("backend-status", handler),
};

const FAILURES: Record<string, string> = {
  already_running: "Another copy of PAW is using your data. Close it, then try again.",
  backend_not_found: "PAW's background service is missing. Reinstalling PAW should fix this.",
  backend_did_not_start: "PAW's background service did not start.",
  backend_exited: "PAW's background service stopped several times.",
  schema_error: "Your data was saved by a newer version of PAW. Update PAW to open it.",
  migration_failed: "PAW could not update its database. Nothing was deleted.",
};

export function describeFailure(code: string): string {
  return FAILURES[code] ?? "PAW could not start.";
}
