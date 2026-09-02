"""Add database-enforced event idempotency and repeat scopes.

Revision ID: 0002_event_uniqueness
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_event_uniqueness"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode recreates the table when required by SQLite while issuing
    # ordinary ALTER TABLE operations on PostgreSQL.
    with op.batch_alter_table("game_events") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(160), nullable=True))
        batch.add_column(sa.Column("repeat_scope", sa.String(16), nullable=False, server_default="ALWAYS"))
        batch.create_check_constraint("ck_game_event_repeat_scope", "repeat_scope IN ('ALWAYS', 'WORLD', 'SPECIES', 'PLAYER')")
        batch.create_check_constraint("ck_game_event_species_scope_subject", "repeat_scope != 'SPECIES' OR species_id IS NOT NULL")
        batch.create_check_constraint("ck_game_event_player_scope_subject", "repeat_scope != 'PLAYER' OR player_id IS NOT NULL")
    op.create_index("uq_game_event_idempotency", "game_events", ["world_id", "code", "idempotency_key"], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL"), sqlite_where=sa.text("idempotency_key IS NOT NULL"))
    op.create_index("uq_game_event_once_world", "game_events", ["world_id", "code"], unique=True, postgresql_where=sa.text("repeat_scope = 'WORLD'"), sqlite_where=sa.text("repeat_scope = 'WORLD'"))
    op.create_index("uq_game_event_once_species", "game_events", ["world_id", "code", "species_id"], unique=True, postgresql_where=sa.text("repeat_scope = 'SPECIES'"), sqlite_where=sa.text("repeat_scope = 'SPECIES'"))
    op.create_index("uq_game_event_once_player", "game_events", ["world_id", "code", "player_id"], unique=True, postgresql_where=sa.text("repeat_scope = 'PLAYER'"), sqlite_where=sa.text("repeat_scope = 'PLAYER'"))


def downgrade() -> None:
    for name in ("uq_game_event_once_player", "uq_game_event_once_species", "uq_game_event_once_world", "uq_game_event_idempotency"):
        op.drop_index(name, table_name="game_events")
    with op.batch_alter_table("game_events") as batch:
        batch.drop_constraint("ck_game_event_player_scope_subject", type_="check")
        batch.drop_constraint("ck_game_event_species_scope_subject", type_="check")
        batch.drop_constraint("ck_game_event_repeat_scope", type_="check")
        batch.drop_column("repeat_scope")
        batch.drop_column("idempotency_key")
