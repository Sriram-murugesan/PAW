import { Brain, LayoutDashboard, Settings, UserRound } from "lucide-react";

/** A page is listed here only once its module works. */
export const PAGES = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "profile", label: "Profile", icon: UserRound },
  { id: "settings", label: "Settings", icon: Settings },
] as const;

export type PageId = (typeof PAGES)[number]["id"];
export type MemoryTab = "confirmed" | "pending" | "archived";
