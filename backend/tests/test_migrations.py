import io

from alembic import command
from alembic.script import ScriptDirectory

from scripts import init_db


def test_alembic_has_single_current_head() -> None:
    script = ScriptDirectory.from_config(init_db.get_alembic_config())

    assert script.get_heads() == ["0004"]
    assert script.get_revision("0001").down_revision is None
    assert script.get_revision("0002").down_revision == "0001"
    assert script.get_revision("0003").down_revision == "0002"


def test_sync_database_url_converts_asyncpg() -> None:
    converted = init_db.sync_database_url(
        "postgresql+asyncpg://foodflow:foodflow@localhost:5432/foodflow"
    )

    assert converted == (
        "postgresql+psycopg2://foodflow:foodflow@localhost:5432/foodflow"
    )
    assert init_db.sync_database_url(converted) == converted


def test_initial_migration_renders_full_schema_offline() -> None:
    config = init_db.get_alembic_config()
    buffer = io.StringIO()
    config.output_buffer = buffer

    command.upgrade(config, "head", sql=True)
    sql = buffer.getvalue()

    assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql
    assert "CREATE TABLE restaurants" in sql
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE orders" in sql
    assert "CREATE TABLE reviews" in sql
    assert "CREATE TABLE events" in sql
    assert "geography(POINT,4326)" in sql
    assert "CREATE INDEX idx_restaurants_location" in sql
    assert "CREATE UNIQUE INDEX ix_reviews_idempotency_key" in sql
    assert "CREATE TABLE user_restaurant_interactions" in sql
    assert "ALTER TABLE restaurants ADD COLUMN source" in sql
    assert "ADD CONSTRAINT uq_restaurants_osm UNIQUE (osm_type, osm_id)" in sql
    assert "CREATE INDEX idx_interactions_user_created" in sql
    assert "INSERT INTO alembic_version" in sql
