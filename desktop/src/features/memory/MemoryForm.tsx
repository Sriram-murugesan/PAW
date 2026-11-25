import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/fields";
import { ErrorNote } from "@/components/ui/misc";
import type { Category, MemoryInput } from "@/services/api";
import { CATEGORIES } from "@/services/format";

interface Props {
  initial?: MemoryInput;
  submitLabel: string;
  busy: boolean;
  error: unknown;
  showSharing?: boolean;
  onSubmit: (value: Required<MemoryInput>) => void;
  onCancel: () => void;
}

export function MemoryForm({ initial, submitLabel, busy, error, showSharing = true, onSubmit, onCancel }: Props) {
  const [value, setValue] = useState<Required<MemoryInput>>({
    category: initial?.category ?? "general_preference",
    title: initial?.title ?? "",
    content: initial?.content ?? "",
    shareable: initial?.shareable ?? true,
  });
  const set = (change: Partial<MemoryInput>) => setValue((old) => ({ ...old, ...change }));
  const complete = value.title.trim() !== "" && value.content.trim() !== "";

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (complete && !busy) onSubmit(value);
      }}
    >
      <Field label="Title">
        {(id) => (
          <Input id={id} autoFocus data-autofocus maxLength={200} value={value.title} onChange={(e) => set({ title: e.target.value })} />
        )}
      </Field>
      <Field label="Category">
        {(id) => (
          <Select id={id} value={value.category} onChange={(e) => set({ category: e.target.value as Category })}>
            {Object.entries(CATEGORIES).map(([key, name]) => (
              <option key={key} value={key}>
                {name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Text">
        {(id) => (
          <Textarea
            id={id}
            maxLength={20_000}
            value={value.content}
            onChange={(e) => set({ content: e.target.value })}
          />
        )}
      </Field>
      {showSharing && (
        <label className="flex items-start gap-2 text-[13px]">
          <input
            type="checkbox"
            className="mt-1 accent-accent"
            checked={value.shareable}
            onChange={(e) => set({ shareable: e.target.checked })}
          />
          <span>
            May be shared with AI tools
            <span className="block text-xs text-faint">
              PAW cannot share anything yet. When it can, you will approve what each tool receives.
            </span>
          </span>
        </label>
      )}
      <ErrorNote error={error} />
      <div className="flex justify-end gap-2">
        <Button onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={!complete || busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
