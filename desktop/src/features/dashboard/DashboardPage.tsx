import type { UseQueryResult } from "@tanstack/react-query";
import { Activity as ActivityIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Empty, ErrorNote, PageLayout, Panel } from "@/components/ui/misc";
import type { MemoryTab } from "@/app/pages";
import type { Dashboard } from "@/services/api";
import { categoryName, eventName, formatDate } from "@/services/format";

interface Props {
  query: UseQueryResult<Dashboard>;
  onOpenMemory: (tab: MemoryTab) => void;
}

export function DashboardPage({ query, onOpenMemory }: Props) {
  const { data, error } = query;
  return (
    <PageLayout title="Dashboard">
      <ErrorNote error={error} />
      {data && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Count label="Confirmed memories" value={data.confirmed_memories} onClick={() => onOpenMemory("confirmed")} />
            <Count label="Waiting for approval" value={data.pending_proposals} onClick={() => onOpenMemory("pending")} />
            <Count label="Archived memories" value={data.archived_memories} onClick={() => onOpenMemory("archived")} />
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <Pending data={data} onOpen={() => onOpenMemory("pending")} />
            <Categories data={data} />
          </div>
          <Recent data={data} />
        </>
      )}
    </PageLayout>
  );
}

function Count({ label, value, onClick }: { label: string; value: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-line bg-panel p-4 text-left hover:bg-raised"
    >
      <span className="block text-2xl font-semibold tabular-nums">{value}</span>
      <span className="text-[13px] text-soft">{label}</span>
    </button>
  );
}

function Pending({ data, onOpen }: { data: Dashboard; onOpen: () => void }) {
  return (
    <Panel>
      <h2 className="mb-3 text-[13px] font-medium text-soft">Waiting for your approval</h2>
      {data.latest_proposals.length === 0 && <p className="text-[13px] text-faint">Nothing to review.</p>}
      <ul className="flex flex-col gap-2">
        {data.latest_proposals.map((p) => (
          <li key={p.id} className="min-w-0 truncate text-[13px]">
            {typeof p.payload["title"] === "string"
              ? p.payload["title"]
              : p.operation === "ARCHIVE"
                ? "Archive a memory"
                : "Change a memory"}
          </li>
        ))}
      </ul>
      {data.pending_proposals > 0 && (
        <Button className="mt-3" onClick={onOpen}>
          Review {data.pending_proposals}
        </Button>
      )}
    </Panel>
  );
}

function Categories({ data }: { data: Dashboard }) {
  const rows = Object.entries(data.memories_by_category).sort((a, b) => b[1] - a[1]);
  return (
    <Panel>
      <h2 className="mb-3 text-[13px] font-medium text-soft">Memories by category</h2>
      {rows.length === 0 && <p className="text-[13px] text-faint">No memories yet.</p>}
      <ul className="flex flex-col gap-1.5 text-[13px]">
        {rows.map(([category, count]) => (
          <li key={category} className="flex justify-between gap-4">
            {categoryName(category)} <span className="text-soft tabular-nums">{count}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Recent({ data }: { data: Dashboard }) {
  if (data.recent_activity.length === 0) {
    return (
      <Empty icon={ActivityIcon} title="No activity yet">
        Add a memory with Ctrl+N, or import a file from Settings.
      </Empty>
    );
  }
  return (
    <Panel>
      <h2 className="mb-3 text-[13px] font-medium text-soft">Recent activity</h2>
      <ul className="flex flex-col gap-1.5 text-[13px]">
        {data.recent_activity.map((event) => (
          <li key={event.id} className="flex justify-between gap-4">
            {eventName(event.event_type)}
            <time className="text-faint" dateTime={event.occurred_at}>
              {formatDate(event.occurred_at)}
            </time>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
