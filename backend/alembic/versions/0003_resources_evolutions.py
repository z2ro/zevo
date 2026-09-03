"""resources and evolution queue"""
from alembic import op
import sqlalchemy as sa

revision = "0003_resources_evolutions"
down_revision = "0002_event_uniqueness"
branch_labels = None
depends_on = None

def upgrade():
    defaults = {"biomass": "1000", "energy": "500", "genetic_material": "50", "adaptation_points": "0"}
    for name, default in defaults.items():
        op.add_column("species", sa.Column(name, sa.Integer(), nullable=False, server_default=default))
    op.create_table("species_evolutions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("species_id", sa.Integer(), sa.ForeignKey("species.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evolution_id", sa.String(80), nullable=False), sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("started_at_tick", sa.Integer(), nullable=False), sa.Column("complete_at_tick", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_species_evolutions_species_id", "species_evolutions", ["species_id"])

def downgrade():
    op.drop_index("ix_species_evolutions_species_id", table_name="species_evolutions"); op.drop_table("species_evolutions")
    for name in ("biomass", "energy", "genetic_material", "adaptation_points"): op.drop_column("species", name)
