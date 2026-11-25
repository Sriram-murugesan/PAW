import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memory, page, problem, proposal, standard, type FakeBackend } from "@/test/fakeBackend";
import { App } from "./App";

let fake: FakeBackend;
vi.mock("@/services/transport", () => ({
  invoke: (cmd: string, args?: Record<string, unknown>) => fake.invoke(cmd, args),
  onEvent: (name: string, handler: never) => fake.onEvent(name, handler),
}));

const user = userEvent.setup();
beforeEach(() => {
  fake = standard();
});

function start() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

async function open(name: string) {
  start();
  const nav = await screen.findByRole("navigation");
  await user.click(within(nav).getByRole("button", { name: new RegExp(name) }));
}

async function openPending() {
  await open("Memory");
  await user.click(screen.getByRole("tab", { name: "Pending" }));
  return screen.findByRole("article");
}

describe("startup", () => {
  it("waits for the backend, then loads", async () => {
    fake.status = { state: "starting" };
    start();
    expect(await screen.findByRole("status")).toHaveTextContent("Starting");
    expect(fake.calls).toEqual([]);
    act(() => fake.emit({ state: "ready" }));
    expect(await screen.findByText("Recent activity")).toBeInTheDocument();
  });

  it("explains a failure and retries", async () => {
    fake.status = { state: "failed", code: "already_running" };
    start();
    expect(await screen.findByRole("alert")).toHaveTextContent("Another copy of PAW");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(fake.commands).toContain("backend_retry");
  });

  it("keeps typed text through a backend restart", async () => {
    await open("Memory");
    await user.click(screen.getByRole("button", { name: "New memory" }));
    await user.type(screen.getByLabelText("Title"), "Half-written");
    act(() => fake.emit({ state: "starting" }));
    expect(screen.getByText(/restarting/)).toBeInTheDocument();
    act(() => fake.emit({ state: "ready" }));
    expect(screen.getByLabelText("Title")).toHaveValue("Half-written");
  });
});

describe("navigation", () => {
  it("lists only working pages", async () => {
    start();
    const names = within(await screen.findByRole("navigation")).getAllByRole("button");
    expect(names.map((n) => n.textContent?.replace(/\d/g, ""))).toEqual(["Dashboard", "Memory", "Profile", "Settings"]);
  });

  it("has keyboard shortcuts", async () => {
    start();
    await screen.findByText("Recent activity");
    await user.keyboard("{Control>}4{/Control}");
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    await user.keyboard("{Control>}n{/Control}");
    expect(screen.getByRole("dialog", { name: "New memory" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveFocus();
  });

  it("shows stored numbers and opens the matching list", async () => {
    start();
    await user.click(await screen.findByRole("button", { name: /Waiting for approval/ }));
    expect(screen.getByRole("tab", { name: "Pending" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("memory", () => {
  it("creates a memory", async () => {
    fake.on("POST", "/api/memory", { data: memory() }, 201);
    await open("Memory");
    await user.click(screen.getByRole("button", { name: "New memory" }));
    const save = screen.getByRole("button", { name: "Save memory" });
    expect(save).toBeDisabled();
    await user.type(screen.getByLabelText("Title"), "T");
    await user.type(screen.getByLabelText("Text"), "Body");
    await user.click(screen.getByLabelText(/May be shared/));
    await user.click(save);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(fake.sent("POST", "/api/memory")[0]?.body).toEqual({
      category: "general_preference",
      title: "T",
      content: "Body",
      shareable: false,
    });
  });

  it("keeps the form and shows why when saving fails", async () => {
    const fields = [{ field: "body.title", message: "too long" }];
    fake.on("POST", "/api/memory", problem("validation_error", "Not valid.", { fields }), 422);
    await open("Memory");
    await user.click(screen.getByRole("button", { name: "New memory" }));
    await user.type(screen.getByLabelText("Title"), "T");
    await user.type(screen.getByLabelText("Text"), "Body");
    await user.click(screen.getByRole("button", { name: "Save memory" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("title: too long");
    expect(screen.getByLabelText("Text")).toHaveValue("Body");
  });

  it("searches and filters", async () => {
    await open("Memory");
    await user.type(screen.getByRole("searchbox"), "c++");
    await user.selectOptions(screen.getByLabelText("Category"), "Weak area");
    await waitFor(() =>
      expect(fake.sent("GET", "/api/memory").at(-1)?.query).toEqual({
        status: "CONFIRMED",
        category: "weak_area",
        q: "c++",
      }),
    );
  });

  it("edits with the version that was read", async () => {
    fake.on("PUT", "/api/memory/m1", problem("version_conflict", "The memory changed since it was read."), 409);
    await open("Memory");
    await user.click(await screen.findByRole("button", { name: /FastAPI/ }));
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    fake.on("GET", "/api/memory/m1", { data: memory({ version: 9 }) });
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("changed since it was read");
    expect(fake.sent("PUT", "/api/memory/m1")[0]?.body).toMatchObject({ version: 1 });
  });

  it("deletes only after confirming, and mentions backups", async () => {
    fake.on("DELETE", "/api/memory/m1", null, 204);
    await open("Memory");
    await user.click(await screen.findByRole("button", { name: /FastAPI/ }));
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(screen.getByText(/Backups made earlier still contain it/)).toBeInTheDocument();
    expect(fake.sent("DELETE", "/api/memory/m1")).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Delete permanently" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(fake.sent("DELETE", "/api/memory/m1")).toHaveLength(1);
  });

  it("shows markup as text", async () => {
    const content = "<img src=x onerror=alert(1)><script>alert(2)</script>";
    fake.on("GET", "/api/memory", page(memory({ content })));
    fake.on("GET", "/api/memory/m1", { data: memory({ content }) });
    await open("Memory");
    await user.click(await screen.findByRole("button", { name: /FastAPI/ }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(content)).toBeInTheDocument();
    expect(document.querySelector("img, script")).toBeNull();
  });

  it("loads more", async () => {
    fake.handle("GET", "/api/memory", ({ query }) => ({
      status: 200,
      body: query["cursor"]
        ? page(memory({ id: "m2", title: "Second" }))
        : { data: [memory()], next_cursor: "next" },
    }));
    await open("Memory");
    await user.click(await screen.findByRole("button", { name: "Show more" }));
    expect(await screen.findByText("Second")).toBeInTheDocument();
    expect(screen.getByText("FastAPI")).toBeInTheDocument();
  });
});

describe("proposals", () => {
  it("shows the full text and who sent it, and approves", async () => {
    fake.on("POST", "/api/memory/proposals/p1/approve", { data: memory() });
    const card = await openPending();
    expect(within(card).getByText("Shipped the bot")).toBeInTheDocument();
    expect(within(card).getByText(/From file import/)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(fake.sent("POST", "/api/memory/proposals/p1/approve")[0]?.body).toEqual({ edits: {} }),
    );
  });

  it("rejects", async () => {
    fake.on("POST", "/api/memory/proposals/p1/reject", { data: proposal({ status: "REJECTED" }) });
    const card = await openPending();
    await user.click(within(card).getByRole("button", { name: "Reject" }));
    await waitFor(() => expect(fake.sent("POST", "/api/memory/proposals/p1/reject")).toHaveLength(1));
  });

  it("approves with corrections", async () => {
    fake.on("POST", "/api/memory/proposals/p1/approve", { data: memory() });
    const card = await openPending();
    await user.click(within(card).getByRole("button", { name: "Edit and approve" }));
    const dialog = screen.getByRole("dialog");
    const title = within(dialog).getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "Better");
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(fake.sent("POST", "/api/memory/proposals/p1/approve")[0]?.body).toEqual({
        edits: { category: "achievement", title: "Better", content: "Shipped the bot" },
      }),
    );
  });

  it("warns about duplicates", async () => {
    fake.on("GET", "/api/memory/proposals", page(proposal({ possible_duplicates: ["m1"] })));
    const card = await openPending();
    expect(within(card).getByText(/already have a memory/)).toBeInTheDocument();
  });

  it("needs a second click to replace newer text", async () => {
    const update = proposal({ operation: "UPDATE", target_id: "m1", base_version: 1, payload: { content: "From agent" } });
    fake.on("GET", "/api/memory/proposals", page(update));
    fake.on("GET", "/api/memory/m1", { data: memory({ version: 2, content: "From user" }) });
    const current = memory({ version: 2 });
    fake.on("POST", "/api/memory/proposals/p1/approve", problem("version_conflict", "Changed.", { current }), 409);
    const card = await openPending();
    expect(await within(card).findByText("From user")).toBeInTheDocument();
    expect(within(card).getByText(/changed since this was proposed/)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Approve" }));
    await user.click(await within(card).findByRole("button", { name: "Replace the newer text" }));
    const sent = fake.sent("POST", "/api/memory/proposals/p1/approve");
    expect(sent.map((c) => (c.body as { current_version?: number }).current_version)).toEqual([undefined, 2]);
  });
});

describe("profile", () => {
  it("saves text and lists, and survives moving away", async () => {
    fake.on("PUT", "/api/profile", { data: { display_name: "B", profile_data: {}, version: 4, updated_at: null } });
    await open("Profile");
    const name = await screen.findByLabelText("Name");
    await user.clear(name);
    await user.type(name, "B");
    await user.keyboard("{Control>}1{/Control}");
    await user.keyboard("{Control>}3{/Control}");
    expect(screen.getByLabelText("Name")).toHaveValue("B");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(fake.sent("PUT", "/api/profile")[0]?.body).toEqual({
      display_name: "B",
      profile_data: { Goals: ["One", "Two"], About: "Text" },
      version: 3,
    });
  });

  it("refuses unnamed or repeated sections", async () => {
    await open("Profile");
    await user.click(await screen.findByRole("button", { name: "Add section" }));
    expect(screen.getByText("Every section needs a name.")).toBeInTheDocument();
    const names = screen.getAllByLabelText("Section name");
    await user.type(names[names.length - 1]!, "Goals");
    expect(screen.getByText("Section names must be different.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });
});

describe("settings", () => {
  it("restores only after confirming", async () => {
    fake.on("POST", "/api/backups/b1/restore", { data: { restored: "b1", safety_backup: "b2" } });
    await open("Settings");
    await user.click(await screen.findByRole("button", { name: /Restore backup/ }));
    expect(fake.sent("POST", "/api/backups/b1/restore")).toEqual([]);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Restore" }));
    expect(await screen.findByText(/backup of what you had/)).toBeInTheDocument();
  });

  it("reports export results", async () => {
    fake.outcomes["export_memories"] = { result: "done", count: 2, skipped: 0 };
    await open("Settings");
    await user.click(await screen.findByRole("button", { name: "Export as JSON" }));
    expect(await screen.findByText("Exported 2 memories.")).toBeInTheDocument();
  });

  it("reports a refused import and opens the review list after a good one", async () => {
    fake.outcomes["import_memories"] = { result: "failed", message: "The file is not valid JSON." };
    await open("Settings");
    await user.click(await screen.findByRole("button", { name: "Import from file" }));
    expect(await screen.findByText("The file is not valid JSON.")).toBeInTheDocument();
    fake.outcomes["import_memories"] = { result: "done", count: 1, skipped: 0 };
    await user.click(screen.getByRole("button", { name: "Import from file" }));
    expect(await screen.findByRole("tab", { name: "Pending" })).toHaveAttribute("aria-selected", "true");
  });

  it("applies the theme", async () => {
    fake.on("GET", "/api/settings", { data: { theme: "light" } });
    await open("Settings");
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
  });
});
