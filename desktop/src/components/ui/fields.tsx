import { useId, type ComponentProps, type ReactNode } from "react";
import { cn } from "./cn";

const box =
  "w-full rounded-md border border-line bg-canvas px-2.5 text-[13px] text-ink placeholder:text-faint";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(box, "h-8", className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={cn(box, "min-h-28 resize-y py-2 leading-relaxed", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cn(box, "h-8", className)} {...props} />;
}

interface FieldProps {
  label: string;
  hint?: string;
  children: (id: string) => ReactNode;
}

export function Field({ label, hint, children }: FieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium text-soft">
        {label}
      </label>
      {children(id)}
      {hint && <p className="text-xs text-faint">{hint}</p>}
    </div>
  );
}
