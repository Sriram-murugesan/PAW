import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Empty, ErrorNote, Panel } from "@/components/ui/misc";
import { useAction } from "@/hooks/useAction";
import { api, ApiError, type MemoryChanges, type MemoryInput, type Proposal } from "@/services/api";
import { categoryName, formatDate, sourceName } from "@/services/format";
import { MemoryForm } from "./MemoryForm";

const OPERATION = { CREATE: "New memory", UPDATE: "Change to a memory", ARCHIVE: "Archive a memory" };

export function ProposalList() {
  const list = useInfiniteQuery({
    queryKey: ["proposals"],
    queryFn: ({ pageParam }) => api.proposals(pageParam),
    initialPageParam: "",
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const proposals = list.data?.pages.flatMap((page) => page.data);
  return (
    <>
      <ErrorNote error={list.error} />
      {proposals?.length === 0 && (
        <Empty icon={Inbox} title="Nothing to review">
          Information from imports and AI tools waits here until you approve it.
        </Empty>
      )}
      {proposals?.map((proposal) => <ProposalCard key={proposal.id} proposal={proposal} />)}
      {list.hasNextPage && (
        <Button className="self-center" disabled={list.isFetching} onClick={() => void list.fetchNextPage()}>
          Show more
        </Button>
      )}
    </>
  );
}

function ProposalCard({ proposal }: { proposal: Proposal }) {
  const [editing, setEditing] = useState(false);
  const [newerVersion, setNewerVersion] = useState<number | null>(null);
  const reject = useAction(() => api.reject(proposal.id));
  const approve = useAction((edits: MemoryChanges) =>
    api
      .approve(proposal.id, { edits, ...(newerVersion === null ? {} : { current_version: newerVersion }) })
      .catch((error: unknown) => {
        // Show the newer memory and require a second, informed click.
        if (error instanceof ApiError && error.code === "version_conflict") {
          setNewerVersion((error.details["current"] as { version: number }).version);
        }
        throw error;
      }),
  );
  const busy = approve.isPending || reject.isPending;
  const payload = proposal.payload as Partial<MemoryInput>;
  const isNew = proposal.operation === "CREATE";
  const title = `${OPERATION[proposal.operation]}${payload.title ? `: ${payload.title}` : ""}`;

  return (
    <Panel>
      <article aria-label={title} className="flex flex-col gap-3">
        <header className="flex flex-wrap items-center gap-1.5">
          <Badge tone="warn">{OPERATION[proposal.operation]}</Badge>
          {payload.category && <Badge>{categoryName(payload.category)}</Badge>}
          <span className="ml-auto text-xs text-faint">
            From {proposal.submitted_by}
            {proposal.sources.map((s) => `, ${sourceName(s.source_type).toLowerCase()}`).join("")},{" "}
            {formatDate(proposal.created_at)}
          </span>
        </header>
        {payload.title && <h3 className="font-medium break-words">{payload.title}</h3>}
        {payload.content && <p className="break-words whitespace-pre-wrap select-text">{payload.content}</p>}
        {proposal.target_id && (
          <Current id={proposal.target_id} base={proposal.base_version} />
        )}
        {proposal.possible_duplicates.length > 0 && (
          <p className="text-[13px] text-warn">You already have a memory with the same text.</p>
        )}
        <ErrorNote error={approve.error ?? reject.error} />
        <div className="flex justify-end gap-2">
          <Button variant="danger" disabled={busy} onClick={() => reject.mutate()}>
            Reject
          </Button>
          {isNew && (
            <Button disabled={busy} onClick={() => setEditing(true)}>
              Edit and approve
            </Button>
          )}
          <Button variant="primary" disabled={busy} onClick={() => approve.mutate({})}>
            {newerVersion === null ? "Approve" : "Replace the newer text"}
          </Button>
        </div>
      </article>
      {editing && (
        <Dialog title="Edit and approve" onClose={() => setEditing(false)}>
          <MemoryForm
            initial={payload as MemoryInput}
            submitLabel="Approve"
            showSharing={false}
            busy={busy}
            error={approve.error}
            onSubmit={({ category, title: newTitle, content }) =>
              approve.mutate({ category, title: newTitle, content })
            }
            onCancel={() => setEditing(false)}
          />
        </Dialog>
      )}
    </Panel>
  );
}

function Current({ id, base }: { id: string; base: number | null }) {
  const { data, error } = useQuery({ queryKey: ["memory", id], queryFn: () => api.memory(id) });
  if (error) return <ErrorNote error={error} />;
  if (!data) return null;
  return (
    <div className="rounded-md border border-line bg-canvas p-3 text-[13px]">
      <p className="text-xs text-faint">
        Your memory now
        {data.version !== base && <span className="text-warn"> (changed since this was proposed)</span>}
      </p>
      <p className="font-medium break-words">{data.title}</p>
      <p className="break-words whitespace-pre-wrap text-soft">{data.content}</p>
    </div>
  );
}
