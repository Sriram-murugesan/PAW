import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "./button";
import { cn } from "./cn";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}

/** The native element supplies focus trapping, Escape and inert background. */
export function Dialog({ title, onClose, children, wide = false }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const element = ref.current;
    if (element && !element.open) {
      element.showModal();
      // showModal focuses the first button, which is Close, after React has applied autoFocus.
      element.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }
    return () => element?.close();
  }, []);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      className={cn(
        "m-auto max-h-[86vh] w-[calc(100%-3rem)] overflow-hidden rounded-xl border border-line bg-panel text-ink shadow-2xl",
        wide ? "max-w-3xl" : "max-w-lg",
      )}
    >
      <div className="flex max-h-[86vh] flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-line px-5 py-3">
          <h2 id={titleId} className="min-w-0 truncate font-semibold">
            {title}
          </h2>
          <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
            <X />
          </Button>
        </header>
        <div className="min-h-0 overflow-y-auto p-5">{children}</div>
      </div>
    </dialog>
  );
}
