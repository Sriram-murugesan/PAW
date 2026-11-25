import { useMutation, useQueryClient } from "@tanstack/react-query";

/** Runs a change, then refreshes everything on screen. The backend is local, so this is cheap. */
export function useAction<A = void, R = unknown>(
  run: (argument: A) => Promise<R>,
  onDone?: (result: R) => void,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (result) => {
      void client.invalidateQueries();
      onDone?.(result);
    },
  });
}
