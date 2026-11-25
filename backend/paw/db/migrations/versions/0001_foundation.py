"""foundation"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TRIGGERS = {
    # Enforced here so that no process can insert a proposal that is already approved,
    # change what the user is reviewing, or reopen a decision.
    "proposals_insert_pending": """
        BEFORE INSERT ON proposals WHEN NEW.status <> 'PENDING'
        BEGIN SELECT RAISE(ABORT, 'new proposals must be pending'); END""",
    "proposals_payload_immutable": """
        BEFORE UPDATE OF payload, operation, target_type, submitted_by, confidence ON proposals
        BEGIN SELECT RAISE(ABORT, 'proposal content is immutable'); END""",
    "proposals_decided_once": """
        BEFORE UPDATE OF status ON proposals WHEN OLD.status <> 'PENDING'
        BEGIN SELECT RAISE(ABORT, 'proposal is already reviewed'); END""",
    "memory_revisions_append_only": """
        BEFORE UPDATE ON memory_revisions
        BEGIN SELECT RAISE(ABORT, 'revisions are append-only'); END""",
}


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.String(length=27), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_events")),
    )
    with op.batch_alter_table("activity_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_activity_events_occurred_at"), ["occurred_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_activity_events_project_id"), ["project_id"], unique=False)

    op.create_table(
        "memories",
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("shareable", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("updated_at", sa.String(length=27), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.CheckConstraint(
            "category IN ('personal_profile', 'technical_skill', 'learning_preference', 'active_project', 'project_architecture', 'technical_decision', 'career_goal', 'learning_history', 'conversation_summary', 'achievement', 'weak_area', 'general_preference')",
            name=op.f("ck_memories_category"),
        ),
        sa.CheckConstraint("status IN ('CONFIRMED', 'ARCHIVED')", name=op.f("ck_memories_status")),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_memories_confidence")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memories")),
    )
    with op.batch_alter_table("memories", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_memories_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_memories_content_hash"), ["content_hash"], unique=False)
        batch_op.create_index("ix_memories_status_updated_at", ["status", "updated_at"], unique=False)

    op.create_table(
        "profile",
        sa.Column("singleton", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("profile_data", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("updated_at", sa.String(length=27), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile")),
        sa.UniqueConstraint("singleton", name=op.f("uq_profile_singleton")),
    )
    op.create_table(
        "proposals",
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("base_version", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("submitted_by", sa.String(length=64), nullable=False),
        sa.Column("reviewed_at", sa.String(length=27), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.CheckConstraint(
            "operation IN ('CREATE', 'UPDATE', 'ARCHIVE')", name=op.f("ck_proposals_operation")
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'SUPERSEDED')", name=op.f("ck_proposals_status")
        ),
        sa.CheckConstraint(
            "target_type IN ('MEMORY', 'PROJECT', 'DECISION', 'LEARNING')",
            name=op.f("ck_proposals_target_type"),
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_proposals_confidence")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposals")),
    )
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.create_index("ix_proposals_status_created_at", ["status", "created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_proposals_target_id"), ["target_id"], unique=False)

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("updated_at", sa.String(length=27), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settings")),
        sa.UniqueConstraint("key", name=op.f("uq_settings_key")),
    )
    op.create_table(
        "memory_revisions",
        sa.Column("memory_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.String(length=32), nullable=False),
        sa.Column("proposal_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["memories.id"], name=op.f("fk_memory_revisions_memory_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["proposals.id"], name=op.f("fk_memory_revisions_proposal_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_revisions")),
        sa.UniqueConstraint("memory_id", "version", name=op.f("uq_memory_revisions_memory_id_version")),
    )
    op.create_table(
        "memory_sources",
        sa.Column("memory_id", sa.String(length=36), nullable=True),
        sa.Column("proposal_id", sa.String(length=36), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=200), nullable=True),
        sa.Column("reference_metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('manual', 'conversation', 'project', 'git', 'learning', 'ai_summary', 'seed')",
            name=op.f("ck_memory_sources_source_type"),
        ),
        sa.CheckConstraint(
            "(memory_id IS NULL) <> (proposal_id IS NULL)", name=op.f("ck_memory_sources_one_owner")
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["memories.id"], name=op.f("fk_memory_sources_memory_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["proposals.id"], name=op.f("fk_memory_sources_proposal_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_sources")),
    )
    with op.batch_alter_table("memory_sources", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_memory_sources_memory_id"), ["memory_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_memory_sources_proposal_id"), ["proposal_id"], unique=False)

    for name, body in TRIGGERS.items():
        op.execute(f"CREATE TRIGGER {name} {body}")


def downgrade() -> None:
    for name in TRIGGERS:
        op.execute(f"DROP TRIGGER {name}")
    with op.batch_alter_table("memory_sources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_memory_sources_proposal_id"))
        batch_op.drop_index(batch_op.f("ix_memory_sources_memory_id"))

    op.drop_table("memory_sources")
    op.drop_table("memory_revisions")
    op.drop_table("settings")
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_proposals_target_id"))
        batch_op.drop_index("ix_proposals_status_created_at")

    op.drop_table("proposals")
    op.drop_table("profile")
    with op.batch_alter_table("memories", schema=None) as batch_op:
        batch_op.drop_index("ix_memories_status_updated_at")
        batch_op.drop_index(batch_op.f("ix_memories_content_hash"))
        batch_op.drop_index(batch_op.f("ix_memories_category"))

    op.drop_table("memories")
    with op.batch_alter_table("activity_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_activity_events_project_id"))
        batch_op.drop_index(batch_op.f("ix_activity_events_occurred_at"))

    op.drop_table("activity_events")
