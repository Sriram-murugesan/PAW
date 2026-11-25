import { PawPrint } from "lucide-react";
import { cn } from "@/components/ui/cn";
import { PAGES, type PageId } from "./pages";

interface Props {
  page: PageId;
  pending: number;
  onGo: (page: PageId) => void;
}

export function Sidebar({ page, pending, onGo }: Props) {
  return (
    <nav aria-label="Main" className="flex w-52 shrink-0 flex-col gap-0.5 border-r border-line bg-panel p-3">
      <div className="flex items-center gap-2 px-2 pt-1 pb-4 font-semibold tracking-tight">
        <PawPrint className="size-4 text-accent" aria-hidden /> PAW
      </div>
      {PAGES.map(({ id, label, icon: Icon }, index) => (
        <button
          key={id}
          type="button"
          aria-current={page === id ? "page" : undefined}
          title={`Ctrl+${index + 1}`}
          onClick={() => onGo(id)}
          className={cn(
            "flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] text-soft hover:bg-raised hover:text-ink",
            page === id && "bg-raised font-medium text-ink",
          )}
        >
          <Icon className="size-4" aria-hidden />
          {label}
          {id === "memory" && pending > 0 && (
            <span className="ml-auto rounded bg-canvas px-1.5 text-xs text-warn" aria-label={`${pending} pending`}>
              {pending}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}
