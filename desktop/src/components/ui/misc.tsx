import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { messageOf } from "@/services/api";
import { cn } from "./cn";

export function Badge({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "warn" | "ok" }) {
  const color = { plain: "text-soft", warn: "text-warn", ok: "text-ok" }[tone];
  return (
    <span className={cn("rounded border border-line bg-raised px-1.5 py-0.5 text-xs whitespace-nowrap", color)}>
      {children}
    </span>
  );
}

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn("rounded-lg border border-line bg-panel p-4", className)}>{children}</section>;
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="rounded-md border border-line bg-raised px-3 py-2 text-[13px] text-danger">
      {messageOf(error)}
    </p>
  );
}

interface EmptyProps {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
}

export function Empty({ icon: Icon, title, children }: EmptyProps) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-line px-6 py-14 text-center">
      <Icon className="size-6 text-faint" aria-hidden />
      <p className="font-medium">{title}</p>
      {children && <div className="max-w-md text-[13px] text-soft">{children}</div>}
    </div>
  );
}

interface PageProps {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}

export function PageLayout({ title, actions, children }: PageProps) {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-8 py-7">
      <header className="flex min-h-8 items-center justify-between gap-4">
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        {actions && <div className="flex gap-2">{actions}</div>}
      </header>
      {children}
    </div>
  );
}
