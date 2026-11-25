import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/fields";
import { ErrorNote, PageLayout, Panel } from "@/components/ui/misc";
import { useAction } from "@/hooks/useAction";
import { api, type Profile, type ProfileData } from "@/services/api";

interface Section {
  key: number;
  name: string;
  text: string;
  isList: boolean;
}

export interface ProfileDraft {
  name: string;
  sections: Section[];
  version: number;
}

let nextKey = 0;

function toDraft(profile: Profile): ProfileDraft {
  const data = profile.profile_data as ProfileData;
  return {
    name: profile.display_name,
    version: profile.version,
    sections: Object.entries(data).map(([name, value]) => ({
      key: nextKey++,
      name,
      text: Array.isArray(value) ? value.join("\n") : value,
      isList: Array.isArray(value),
    })),
  };
}

function toData(sections: Section[]): ProfileData {
  return Object.fromEntries(
    sections.map(({ name, text, isList }) => [
      name.trim(),
      isList ? text.split("\n").map((line) => line.trim()).filter(Boolean) : text.trim(),
    ]),
  );
}

interface Props {
  /** Kept by the parent so that moving to another page does not lose it. */
  draft: ProfileDraft | null;
  onDraft: (draft: ProfileDraft | null) => void;
}

export function ProfilePage({ draft, onDraft }: Props) {
  const { data, error, refetch } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const [saved, setSaved] = useState(false);
  const save = useAction(
    (value: ProfileDraft) =>
      api.saveProfile({ display_name: value.name, profile_data: toData(value.sections), version: value.version }),
    () => {
      onDraft(null);
      setSaved(true);
    },
  );
  const value = draft ?? (data ? toDraft(data) : null);
  if (!value) {
    return (
      <PageLayout title="Profile">
        <ErrorNote error={error} />
      </PageLayout>
    );
  }

  const change = (next: Partial<ProfileDraft>) => {
    setSaved(false);
    onDraft({ ...value, ...next });
  };
  const changeSection = (key: number, next: Partial<Section>) =>
    change({ sections: value.sections.map((s) => (s.key === key ? { ...s, ...next } : s)) });
  const names = value.sections.map((s) => s.name.trim());
  const problem = names.includes("")
    ? "Every section needs a name."
    : new Set(names).size < names.length
      ? "Section names must be different."
      : null;

  return (
    <PageLayout
      title="Profile"
      actions={
        <>
          {draft && (
            <Button
              onClick={() => {
                save.reset();
                onDraft(null);
                void refetch();
              }}
            >
              Discard changes
            </Button>
          )}
          <Button
            variant="primary"
            disabled={!draft || problem !== null || save.isPending}
            onClick={() => save.mutate(value)}
          >
            Save
          </Button>
        </>
      }
    >
      <p className="text-[13px] text-soft">
        Everything here is yours to write and change. PAW assumes nothing about you.
      </p>
      <Panel className="flex flex-col gap-4">
        <Field label="Name">
          {(id) => (
            <Input id={id} maxLength={200} value={value.name} onChange={(e) => change({ name: e.target.value })} />
          )}
        </Field>
      </Panel>
      {value.sections.map((section) => (
        <Panel key={section.key} className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Input
              aria-label="Section name"
              placeholder="Section name, such as Goals"
              maxLength={64}
              value={section.name}
              onChange={(e) => changeSection(section.key, { name: e.target.value })}
            />
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Remove section ${section.name}`}
              onClick={() => change({ sections: value.sections.filter((s) => s.key !== section.key) })}
            >
              <Trash2 />
            </Button>
          </div>
          <Textarea
            aria-label={`Text of ${section.name || "new section"}`}
            value={section.text}
            onChange={(e) => changeSection(section.key, { text: e.target.value })}
          />
          {section.isList && <p className="text-xs text-faint">One item per line.</p>}
        </Panel>
      ))}
      <Button
        className="self-start"
        onClick={() =>
          change({ sections: [...value.sections, { key: nextKey++, name: "", text: "", isList: false }] })
        }
      >
        <Plus /> Add section
      </Button>
      {problem && <p className="text-[13px] text-warn">{problem}</p>}
      <ErrorNote error={save.error} />
      <p role="status" className="text-[13px] text-ok">
        {saved && !draft ? "Saved." : ""}
      </p>
    </PageLayout>
  );
}
