/**
 * Development only: lets the interface run in an ordinary browser against a real backend.
 * Uses a throwaway data directory, never the user's own data. Not part of any build.
 */
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";

interface Call {
  cmd: string;
  args?: { method: string; path: string; query: Record<string, string>; body?: unknown };
}

export function backendHarness(): Plugin {
  return {
    name: "paw-backend-harness",
    apply: "serve",
    configureServer(server) {
      const home = mkdtempSync(join(tmpdir(), "paw-harness-"));
      const token = randomBytes(32).toString("hex");
      const program = fileURLToPath(new URL("../../.venv/bin/paw-backend", import.meta.url));
      const child = spawn(program, ["serve"], {
        env: { ...process.env, XDG_DATA_HOME: home },
        stdio: ["pipe", "pipe", "ignore"],
      });
      child.stdin.write(`${token}\n`);
      const port = new Promise<number>((resolve, reject) => {
        createInterface(child.stdout).once("line", (line) => {
          const hello = JSON.parse(line) as { event: string; port?: number };
          if (hello.port) resolve(hello.port);
          else reject(new Error(line));
        });
      });
      const stop = () => {
        child.stdin.end();
        rmSync(home, { recursive: true, force: true });
      };
      server.httpServer?.once("close", stop);
      process.once("exit", stop);
      process.once("SIGTERM", () => process.exit(0));

      server.middlewares.use("/__paw", (request, response) => {
        let text = "";
        request.on("data", (chunk) => (text += chunk));
        request.on("end", () => {
          void answer(JSON.parse(text) as Call).then((result) => {
            response.setHeader("content-type", "application/json");
            response.end(JSON.stringify(result ?? null));
          });
        });
      });

      async function answer({ cmd, args }: Call): Promise<unknown> {
        if (cmd === "backend_status") return port.then(() => ({ state: "ready" }));
        if (cmd !== "api_request" || !args) {
          return { result: "failed", message: "Only available in the desktop app." };
        }
        const url = new URL(`http://127.0.0.1:${await port}${args.path}`);
        for (const [key, value] of Object.entries(args.query)) url.searchParams.set(key, value);
        const result = await fetch(url, {
          method: args.method,
          headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
          ...(args.body == null ? {} : { body: JSON.stringify(args.body) }),
        });
        const body = await result.text();
        const parsed: unknown = body ? JSON.parse(body) : null;
        return { status: result.status, body: parsed };
      }
    },
  };
}
