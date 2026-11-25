from enum import StrEnum


class MemoryCategory(StrEnum):
    PERSONAL_PROFILE = "personal_profile"
    TECHNICAL_SKILL = "technical_skill"
    LEARNING_PREFERENCE = "learning_preference"
    ACTIVE_PROJECT = "active_project"
    PROJECT_ARCHITECTURE = "project_architecture"
    TECHNICAL_DECISION = "technical_decision"
    CAREER_GOAL = "career_goal"
    LEARNING_HISTORY = "learning_history"
    CONVERSATION_SUMMARY = "conversation_summary"
    ACHIEVEMENT = "achievement"
    WEAK_AREA = "weak_area"
    GENERAL_PREFERENCE = "general_preference"


class MemoryStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    ARCHIVED = "ARCHIVED"


class ProposalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ProposalTarget(StrEnum):
    MEMORY = "MEMORY"
    PROJECT = "PROJECT"
    DECISION = "DECISION"
    LEARNING = "LEARNING"


class ProposalOperation(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    ARCHIVE = "ARCHIVE"


class SourceType(StrEnum):
    MANUAL = "manual"
    CONVERSATION = "conversation"
    PROJECT = "project"
    GIT = "git"
    LEARNING = "learning"
    AI_SUMMARY = "ai_summary"
    SEED = "seed"
