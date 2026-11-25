import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/app/App";
import "./styles.css";

const client = new QueryClient({
  // The backend is on this machine, so browser online detection must not pause requests.
  defaultOptions: {
    queries: { networkMode: "always", retry: 1, staleTime: 30_000, refetchOnWindowFocus: true },
    mutations: { networkMode: "always", retry: false },
  },
});

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
}
