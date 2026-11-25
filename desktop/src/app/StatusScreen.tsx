import { PawPrint } from "lucide-react";
import { Button } from "@/components/ui/button";
import { backend, describeFailure, type BackendStatus } from "@/services/backend";

export function StatusScreen({ status }: { status: BackendStatus }) {
  return (
    <main className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
      <PawPrint className="size-8 text-accent" aria-hidden />
      {status.state === "failed" ? (
        <>
          <h1 className="text-base font-semibold">PAW could not start</h1>
          <p role="alert" className="max-w-md text-soft">
            {describeFailure(status.code)}
          </p>
          <p className="text-xs text-faint select-text">
            Details are in paw/logs/paw.log, in your data folder (normally ~/.local/share). Code: {status.code}
          </p>
          <Button variant="primary" onClick={() => void backend.retry()}>
            Try again
          </Button>
        </>
      ) : (
        <p role="status" className="text-soft">
          {status.state === "stopped" ? "Stopping…" : "Starting…"}
        </p>
      )}
    </main>
  );
}
