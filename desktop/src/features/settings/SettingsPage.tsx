import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Select } from "@/components/ui/fields";
import { ErrorNote, PageLayout, Panel } from "@/components/ui/misc";
import { useAction } from "@/hooks/useAction";
import { api, type Backup, type FileOutcome, type Settings } from "@/services/api";
import { formatDate, formatSize } from "@/services/format";

export function SettingsPage({ onImported }: { onImported: () => void }) {
  return (
    <PageLayout title="Settings">
      <Appearance />
      <Files onImported={onImported} />
      <Backups />
      <Privacy />
    </PageLayout>
  );
}

function Appearance() {
  const { data, error } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const save = useAction(api.saveSettings);
  return (
    <Panel className="flex flex-col gap-3">
      <h2 className="font-medium">Appearance</h2>
      <Field label="Theme">
        {(id) => (
          <Select
            id={id}
            className="w-52"
            value={data?.theme ?? "dark"}
            disabled={!data || save.isPending}
            onChange={(e) => save.mutate({ theme: e.target.value as NonNullable<Settings["theme"]> })}
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
            <option value="system">Match the system</option>
          </Select>
        )}
      </Field>
      <ErrorNote error={error ?? save.error} />
    </Panel>
  );
}

function Files({ onImported }: { onImported: () => void }) {
  const [message, setMessage] = useState<string | null>(null);
  const report = (describe: (outcome: Extract<FileOutcome, { result: "done" }>) => string) => (outcome: FileOutcome) => {
    if (outcome.result === "done") setMessage(describe(outcome));
    else setMessage(outcome.result === "failed" ? outcome.message : null);
  };
  const exporting = useAction(
    api.exportMemories,
    report(({ count }) => `Exported ${count} ${count === 1 ? "memory" : "memories"}.`),
  );
  const importing = useAction(api.importMemories, (outcome) => {
    report(({ count, skipped }) => `Added ${count} to review${skipped ? `, skipped ${skipped} already known` : ""}.`)(outcome);
    if (outcome.result === "done" && outcome.count > 0) onImported();
  });
  const busy = exporting.isPending || importing.isPending;
  return (
    <Panel className="flex flex-col gap-3">
      <h2 className="font-medium">Export and import</h2>
      <p className="text-[13px] text-soft">
        An export is an ordinary file that anyone with access to it can read. Imported items wait for your approval.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => exporting.mutate("json")}>
          Export as JSON
        </Button>
        <Button disabled={busy} onClick={() => exporting.mutate("markdown")}>
          Export as Markdown
        </Button>
        <Button disabled={busy} onClick={() => importing.mutate()}>
          Import from file
        </Button>
      </div>
      <p role="status" className="text-[13px] text-soft">
        {message}
      </p>
      <ErrorNote error={exporting.error ?? importing.error} />
    </Panel>
  );
}

const REASON: Record<string, string> = {
  manual: "Made by you",
  "pre-migration": "Before an update",
  "pre-restore": "Before a restore",
};

function Backups() {
  const { data, error } = useQuery({ queryKey: ["backups"], queryFn: api.backups });
  const [chosen, setChosen] = useState<Backup | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const create = useAction(api.createBackup, () => setMessage("Backup made."));
  return (
    <Panel className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="font-medium">Backups</h2>
        <Button disabled={create.isPending} onClick={() => create.mutate()}>
          Back up now
        </Button>
      </div>
      <p className="text-[13px] text-soft">
        Stored on this computer, unencrypted. Backups keep memories you delete later.
      </p>
      <p role="status" className="text-[13px] text-ok">
        {message}
      </p>
      <ErrorNote error={error ?? create.error} />
      {data?.length === 0 && <p className="text-[13px] text-faint">No backups yet.</p>}
      <ul className="divide-y divide-line">
        {data?.map((backup) => (
          <li key={backup.id} className="flex items-center gap-4 py-2 text-[13px]">
            <span className="flex-1">{formatDate(backup.created_at)}</span>
            <span className="text-soft">{REASON[backup.reason] ?? backup.reason}</span>
            <span className="w-16 text-right text-faint tabular-nums">{formatSize(backup.size_bytes)}</span>
            <Button aria-label={`Restore backup from ${formatDate(backup.created_at)}`} onClick={() => setChosen(backup)}>
              Restore
            </Button>
          </li>
        ))}
      </ul>
      {chosen && (
        <RestoreDialog
          backup={chosen}
          onClose={() => setChosen(null)}
          onRestored={() => {
            setChosen(null);
            setMessage("Restored. A backup of what you had before was made.");
          }}
        />
      )}
    </Panel>
  );
}

interface RestoreProps {
  backup: Backup;
  onClose: () => void;
  onRestored: () => void;
}

function RestoreDialog({ backup, onClose, onRestored }: RestoreProps) {
  const restore = useAction(() => api.restoreBackup(backup.id), onRestored);
  return (
    <Dialog title="Restore backup" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <p>
          Replace everything in PAW with the backup from <strong>{formatDate(backup.created_at)}</strong>?
        </p>
        <p className="text-[13px] text-soft">Your current data is backed up first, so you can go back.</p>
        <ErrorNote error={restore.error} />
        <div className="flex justify-end gap-2">
          <Button autoFocus data-autofocus onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" disabled={restore.isPending} onClick={() => restore.mutate()}>
            Restore
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function Privacy() {
  return (
    <Panel className="flex flex-col gap-2">
      <h2 className="font-medium">Privacy</h2>
      <ul className="flex list-disc flex-col gap-1 pl-5 text-[13px] text-soft">
        <li>Your data stays on this computer. This version sends nothing to AI providers.</li>
        <li>The database is not encrypted. Other programs running under your account can read it.</li>
      </ul>
    </Panel>
  );
}
