import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { MemoryPage } from "@/features/memory/MemoryPage";
import { ProfilePage, type ProfileDraft } from "@/features/profile/ProfilePage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { useBackendStatus } from "@/hooks/useBackendStatus";
import { useTheme } from "@/hooks/useTheme";
import { api } from "@/services/api";
import { PAGES, type MemoryTab, type PageId } from "./pages";
import { Sidebar } from "./Sidebar";
import { StatusScreen } from "./StatusScreen";

export function App() {
  const status = useBackendStatus();
  // Once running, stay on screen through a restart so that nothing being typed is lost.
  const [everReady, setEverReady] = useState(false);
  if (status.state === "ready" && !everReady) setEverReady(true);

  if (!everReady) return <StatusScreen status={status} />;
  return (
    <div className="flex h-full flex-col">
      {status.state !== "ready" && <ReconnectBar failed={status.state === "failed"} />}
      <div className="min-h-0 flex-1">
        <Workspace />
      </div>
      {status.state === "failed" && (
        <div className="fixed inset-0 bg-canvas">
          <StatusScreen status={status} />
        </div>
      )}
    </div>
  );
}

function ReconnectBar({ failed }: { failed: boolean }) {
  if (failed) return null;
  return (
    <p role="status" className="border-b border-line bg-raised px-4 py-1.5 text-center text-xs text-warn">
      PAW's background service is restarting…
    </p>
  );
}

function Workspace() {
  const [page, setPage] = useState<PageId>("dashboard");
  const [tab, setTab] = useState<MemoryTab>("confirmed");
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  useTheme();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.ctrlKey || event.altKey || event.shiftKey || document.querySelector("dialog[open]")) return;
      const target = PAGES[Number(event.key) - 1];
      if (target) setPage(target.id);
      else if (event.key === "n") {
        setPage("memory");
        setCreating(true);
      } else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const openMemory = (next: MemoryTab) => {
    setTab(next);
    setPage("memory");
  };

  return (
    <div className="flex h-full">
      <Sidebar page={page} pending={dashboard.data?.pending_proposals ?? 0} onGo={setPage} />
      <main className="min-w-0 flex-1 overflow-y-auto">
        {page === "dashboard" && <DashboardPage query={dashboard} onOpenMemory={openMemory} />}
        {page === "memory" && (
          <MemoryPage tab={tab} onTab={setTab} creating={creating} onCreating={setCreating} />
        )}
        {page === "profile" && <ProfilePage draft={draft} onDraft={setDraft} />}
        {page === "settings" && <SettingsPage onImported={() => openMemory("pending")} />}
      </main>
    </div>
  );
}
