import { invoke as tauriInvoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (isTauri()) return tauriInvoke<T>(cmd, args);
  if (import.meta.env.DEV) {
    const response = await fetch("/__paw", { method: "POST", body: JSON.stringify({ cmd, args }) });
    return (await response.json()) as T;
  }
  throw new Error("PAW must run as a desktop app.");
}

export async function onEvent<T>(name: string, handler: (payload: T) => void): Promise<() => void> {
  if (!isTauri()) return () => undefined;
  return listen<T>(name, (event) => handler(event.payload));
}
