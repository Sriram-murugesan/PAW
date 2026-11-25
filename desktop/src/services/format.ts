import type { Category } from "./api";

export const CATEGORIES: Record<Category, string> = {
  personal_profile: "Personal profile",
  technical_skill: "Technical skill",
  learning_preference: "Learning preference",
  active_project: "Active project",
  project_architecture: "Project architecture",
  technical_decision: "Technical decision",
  career_goal: "Career goal",
  learning_history: "Learning history",
  conversation_summary: "Conversation summary",
  achievement: "Achievement",
  weak_area: "Weak area",
  general_preference: "General preference",
};

export const categoryName = (value: unknown) => CATEGORIES[value as Category] ?? String(value);

const SOURCES: Record<string, string> = {
  manual: "Entered by you",
  conversation: "Conversation",
  project: "Project",
  git: "Git",
  learning: "Learning session",
  ai_summary: "AI summary",
  seed: "Imported file",
};
export const sourceName = (value: string) => SOURCES[value] ?? value;

const EVENTS: Record<string, string> = {
  "memory.created": "Memory created",
  "memory.edited": "Memory edited",
  "memory.archived": "Memory archived",
  "memory.unarchived": "Memory moved back to confirmed",
  "memory.deleted": "Memory deleted",
  "memory.proposal_approved": "Memory saved from a proposal",
  "proposal.submitted": "Proposal received",
  "proposal.approved": "Proposal approved",
  "proposal.rejected": "Proposal rejected",
  "profile.updated": "Profile updated",
  "backup.created": "Backup created",
  "backup.restored": "Backup restored",
};
export const eventName = (value: string) => EVENTS[value] ?? value;

const REASONS: Record<string, string> = {
  created: "Created",
  edited: "Edited",
  archived: "Archived",
  unarchived: "Moved back to confirmed",
  proposal_approved: "Approved proposal",
};
export const reasonName = (value: string) => REASONS[value] ?? value;

const formatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
export const formatDate = (value: string) => formatter.format(new Date(value));

export function formatSize(bytes: number): string {
  return bytes < 1_000_000 ? `${Math.ceil(bytes / 1000)} kB` : `${(bytes / 1_000_000).toFixed(1)} MB`;
}
