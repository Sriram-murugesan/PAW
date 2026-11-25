import { useInfiniteQuery } from "@tanstack/react-query";
import { Brain, Plus, Search } from "lucide-react";
import { useDeferredValue, useEffect, useRef, useState } from "react";
import type { MemoryTab } from "@/app/pages";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Dialog } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/fields";
import { Badge, Empty, ErrorNote, PageLayout } from "@/components/ui/misc";
import { useAction } from "@/hooks/useAction";
import { api, type Memory } from "@/services/api";
import { CATEGORIES, categoryName, formatDate } from "@/services/format";
import { MemoryDialog } from "./MemoryDialog";
import { MemoryForm } from "./MemoryForm";
import { ProposalList } from "./ProposalList";

interface Props {
  tab: MemoryTab;
  onTab: (tab: MemoryTab) => void;
  creating: boolean;
  onCreating: (open: boolean) => void;
}

const TABS: { id: MemoryTab; label: string }[] = [
  { id: "confirmed", label: "Confirmed" },
  { id: "pending", label: "Pending" },
  { id: "archived", label: "Archived" },
];

export function MemoryPage({ tab, onTab, creating, onCreating }: Props) {
  const create = useAction(api.createMemory, () => {
    onCreating(false);
    onTab("confirmed");
  });
  return (
    <PageLayout
      title="Memory"
      actions={
        <Button variant="primary" onClick={() => onCreating(true)} title="Ctrl+N">
          <Plus /> New memory
        </Button>
      }
    >
      <div role="tablist" aria-label="Memory state" className="flex gap-1 border-b border-line">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => onTab(id)}
            className={cn(
              "-mb-px border-b-2 border-transparent px-3 py-2 text-[13px] text-soft hover:text-ink",
              tab === id && "border-accent font-medium text-ink",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "pending" ? <ProposalList /> : <MemoryList key={tab} archived={tab === "archived"} />}
      {creating && (
        <Dialog title="New memory" onClose={() => onCreating(false)}>
          <MemoryForm
            submitLabel="Save memory"
            busy={create.isPending}
            error={create.error}
            onSubmit={create.mutate}
            onCancel={() => onCreating(false)}
          />
        </Dialog>
      )}
    </PageLayout>
  );
}

function MemoryList({ archived }: { archived: boolean }) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const q = useDeferredValue(text.trim());
  const status = archived ? "ARCHIVED" : "CONFIRMED";

  const list = useInfiniteQuery({
    queryKey: ["memories", status, category, q],
    queryFn: ({ pageParam }) => api.memories({ status, category, q, cursor: pageParam }),
    initialPageParam: "",
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    placeholderData: (previous) => previous,
  });
  const memories = list.data?.pages.flatMap((page) => page.data);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = event.target instanceof HTMLElement && event.target.matches("input, textarea, select");
      if (event.key !== "/" || typing || document.querySelector("dialog[open]")) return;
      event.preventDefault();
      search.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-2 left-2.5 size-4 text-faint" aria-hidden />
          <Input
            ref={search}
            type="search"
            aria-label="Search memories"
            placeholder="Search titles and text ( / )"
            maxLength={500}
            className="pl-8"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </div>
        <Select
          aria-label="Category"
          className="w-52"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="">All categories</option>
          {Object.entries(CATEGORIES).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </Select>
      </div>
      <ErrorNote error={list.error} />
      {memories?.length === 0 && (
        <Empty icon={Brain} title={q || category ? "Nothing matches" : archived ? "Nothing archived" : "No memories yet"}>
          {!q && !category && !archived && "PAW keeps only what you enter or approve."}
        </Empty>
      )}
      {memories && memories.length > 0 && (
        <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-panel">
          {memories.map((memory) => (
            <MemoryRow key={memory.id} memory={memory} onOpen={() => setOpenId(memory.id)} />
          ))}
        </ul>
      )}
      {list.hasNextPage && (
        <Button className="self-center" disabled={list.isFetching} onClick={() => void list.fetchNextPage()}>
          Show more
        </Button>
      )}
      {openId && <MemoryDialog id={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}

function MemoryRow({ memory, onOpen }: { memory: Memory; onOpen: () => void }) {
  return (
    <li>
      <button type="button" onClick={onOpen} className="flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-raised">
        <span className="flex w-full items-center gap-2">
          <span className="min-w-0 flex-1 truncate font-medium">{memory.title}</span>
          {!memory.shareable && <Badge tone="warn">Private</Badge>}
          <Badge>{categoryName(memory.category)}</Badge>
        </span>
        <span className="line-clamp-2 text-[13px] text-soft">{memory.content}</span>
        <time className="text-xs text-faint" dateTime={memory.updated_at}>
          Updated {formatDate(memory.updated_at)}
        </time>
      </button>
    </li>
  );
}
