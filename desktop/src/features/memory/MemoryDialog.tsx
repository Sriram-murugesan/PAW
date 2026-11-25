import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, ErrorNote } from "@/components/ui/misc";
import { useAction } from "@/hooks/useAction";
import { api, type MemoryDetail } from "@/services/api";
import { categoryName, formatDate, reasonName, sourceName } from "@/services/format";
import { MemoryForm } from "./MemoryForm";

type Mode = "view" | "edit" | "delete";

export function MemoryDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const [mode, setMode] = useState<Mode>("view");
  const { data, error } = useQuery({ queryKey: ["memory", id], queryFn: () => api.memory(id) });
  const title = { view: data?.title ?? "Memory", edit: "Edit memory", delete: "Delete memory" }[mode];
  return (
    <Dialog title={title} onClose={onClose} wide={mode === "view"}>
      <ErrorNote error={error} />
      {data && mode === "view" && <View memory={data} onMode={setMode} onClose={onClose} />}
      {data && mode === "edit" && <Edit memory={data} onDone={() => setMode("view")} />}
      {data && mode === "delete" && <Delete memory={data} onCancel={() => setMode("view")} onDeleted={onClose} />}
    </Dialog>
  );
}

interface ViewProps {
  memory: MemoryDetail;
  onMode: (mode: Mode) => void;
  onClose: () => void;
}

function View({ memory, onMode, onClose }: ViewProps) {
  const archived = memory.status === "ARCHIVED";
  const setArchived = useAction(() => api.setArchived(memory.id, !archived), onClose);
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap gap-1.5">
        <Badge>{categoryName(memory.category)}</Badge>
        <Badge tone={archived ? "plain" : "ok"}>{archived ? "Archived" : "Confirmed"}</Badge>
        <Badge tone={memory.shareable ? "plain" : "warn"}>{memory.shareable ? "May be shared" : "Private"}</Badge>
      </div>
      <p className="leading-relaxed break-words whitespace-pre-wrap select-text">{memory.content}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
        <dt className="text-faint">Created</dt>
        <dd>{formatDate(memory.created_at)}</dd>
        <dt className="text-faint">Updated</dt>
        <dd>{formatDate(memory.updated_at)}</dd>
        <dt className="text-faint">Source</dt>
        <dd>
          {memory.sources.map((source) => (
            <span key={source.id} className="block">
              {sourceName(source.source_type)}
              {source.source_id && ` (${source.source_id})`}
            </span>
          ))}
        </dd>
      </dl>
      <History id={memory.id} />
      <ErrorNote error={setArchived.error} />
      <div className="flex justify-end gap-2">
        <Button variant="danger" onClick={() => onMode("delete")}>
          Delete
        </Button>
        <Button disabled={setArchived.isPending} onClick={() => setArchived.mutate()}>
          {archived ? "Move to confirmed" : "Archive"}
        </Button>
        <Button variant="primary" onClick={() => onMode("edit")}>
          Edit
        </Button>
      </div>
    </div>
  );
}

function History({ id }: { id: string }) {
  const { data, error } = useQuery({ queryKey: ["history", id], queryFn: () => api.history(id) });
  return (
    <details>
      <summary className="cursor-pointer text-[13px] text-soft">History{data && ` (${data.length})`}</summary>
      <ErrorNote error={error} />
      <ol className="mt-2 flex flex-col gap-2">
        {data?.map((revision) => (
          <li key={revision.id} className="rounded-md border border-line bg-canvas p-3 text-[13px]">
            <p className="text-xs text-faint">
              Version {revision.version}, {reasonName(revision.change_reason).toLowerCase()},{" "}
              {formatDate(revision.created_at)}
            </p>
            <p className="font-medium">{String(revision.snapshot["title"])}</p>
            <p className="break-words whitespace-pre-wrap text-soft select-text">{String(revision.snapshot["content"])}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}

function Edit({ memory, onDone }: { memory: MemoryDetail; onDone: () => void }) {
  // The version read when editing began, so that a change made meanwhile is never overwritten.
  const [version] = useState(memory.version);
  const save = useAction(
    (value: Parameters<typeof api.createMemory>[0]) => api.updateMemory(memory.id, { ...value, version }),
    onDone,
  );
  return (
    <MemoryForm
      initial={memory}
      submitLabel="Save changes"
      busy={save.isPending}
      error={save.error}
      onSubmit={save.mutate}
      onCancel={onDone}
    />
  );
}

interface DeleteProps {
  memory: MemoryDetail;
  onCancel: () => void;
  onDeleted: () => void;
}

function Delete({ memory, onCancel, onDeleted }: DeleteProps) {
  const remove = useAction(() => api.deleteMemory(memory.id), onDeleted);
  return (
    <div className="flex flex-col gap-4">
      <p>
        Delete <strong className="break-words">{memory.title}</strong>, its history and its proposals? This cannot be undone.
      </p>
      <p className="text-[13px] text-soft">
        Backups made earlier still contain it. Archive it instead to keep it out of the way.
      </p>
      <ErrorNote error={remove.error} />
      <div className="flex justify-end gap-2">
        <Button autoFocus data-autofocus onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
          Delete permanently
        </Button>
      </div>
    </div>
  );
}
