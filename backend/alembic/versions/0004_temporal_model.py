"""separate planet age from simulation step and species generations

Revision ID: 0004_temporal_model
Revises: 0003_resources_evolutions
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_temporal_model"
down_revision = "0003_resources_evolutions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("worlds", sa.Column("age_years", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("worlds", sa.Column("last_simulated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE worlds SET age_years = COALESCE(generation, tick * 1000, 0), last_simulated_at = CURRENT_TIMESTAMP")
    op.alter_column("worlds", "last_simulated_at", nullable=False)
    op.alter_column("worlds", "age_years", server_default=None)
    op.alter_column("world_snapshots", "generation", new_column_name="age_years", type_=sa.BigInteger())
    op.alter_column("game_events", "generation", new_column_name="planet_age_years", type_=sa.BigInteger())
    op.alter_column("historical_flags", "generation", new_column_name="planet_age_years", type_=sa.BigInteger())
    op.alter_column("player_actions", "execute_at_tick", new_column_name="execute_at_year", type_=sa.BigInteger())
    op.execute("UPDATE player_actions SET execute_at_year = execute_at_year * 1000 WHERE execute_at_year IS NOT NULL")
    op.alter_column("species_evolutions", "started_at_tick", new_column_name="started_at_year", type_=sa.BigInteger())
    op.alter_column("species_evolutions", "complete_at_tick", new_column_name="complete_at_year", type_=sa.BigInteger())
    op.execute("UPDATE species_evolutions SET started_at_year = started_at_year * 1000, complete_at_year = complete_at_year * 1000")


def downgrade() -> None:
    op.execute("UPDATE species_evolutions SET started_at_year = started_at_year / 1000, complete_at_year = complete_at_year / 1000")
    op.alter_column("species_evolutions", "complete_at_year", new_column_name="complete_at_tick", type_=sa.Integer())
    op.alter_column("species_evolutions", "started_at_year", new_column_name="started_at_tick", type_=sa.Integer())
    op.execute("UPDATE player_actions SET execute_at_year = execute_at_year / 1000 WHERE execute_at_year IS NOT NULL")
    op.alter_column("player_actions", "execute_at_year", new_column_name="execute_at_tick", type_=sa.Integer())
    op.alter_column("historical_flags", "planet_age_years", new_column_name="generation", type_=sa.Integer())
    op.alter_column("game_events", "planet_age_years", new_column_name="generation", type_=sa.Integer())
    op.alter_column("world_snapshots", "age_years", new_column_name="generation", type_=sa.Integer())
    op.drop_column("worlds", "last_simulated_at")
    op.drop_column("worlds", "age_years")
