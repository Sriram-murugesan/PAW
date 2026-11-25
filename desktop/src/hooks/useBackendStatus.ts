import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { backend, type BackendStatus } from "@/services/backend";

export function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>({ state: "starting" });
  const client = useQueryClient();

  useEffect(() => {
    let active = true;
    let heard = false;
    const apply = (next: BackendStatus) => {
      if (!active) return;
      setStatus(next);
      if (next.state === "ready") void client.invalidateQueries();
    };
    const unlisten = backend.onStatus((next) => {
      heard = true;
      apply(next);
    });
    // Ask only after listening, and let any event win over the older answer.
    void unlisten
      .then(() => backend.status())
      .then((current) => {
        if (!heard) apply(current);
      })
      .catch(() => apply({ state: "failed", code: "unknown" }));
    return () => {
      active = false;
      void unlisten.then((stop) => stop());
    };
  }, [client]);

  return status;
}
