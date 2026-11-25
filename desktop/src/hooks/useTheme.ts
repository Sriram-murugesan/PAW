import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/services/api";

export function useTheme() {
  const { data } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const theme = data?.theme ?? "dark";
  useEffect(() => {
    const system = window.matchMedia("(prefers-color-scheme: light)");
    const apply = () => {
      const light = theme === "light" || (theme === "system" && system.matches);
      document.documentElement.dataset.theme = light ? "light" : "dark";
    };
    apply();
    system.addEventListener("change", apply);
    return () => system.removeEventListener("change", apply);
  }, [theme]);
}
