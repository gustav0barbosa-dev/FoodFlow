from sqlalchemy.dialects import postgresql

from app.crud import build_search_statement
from app.schemas import RestaurantSearchParams


def test_search_statement_uses_postgis_geography() -> None:
    params = RestaurantSearchParams(lat=-23.5325, lon=-46.7939, radius_km=5)
    statement = build_search_statement(params)

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "ST_DWithin" in sql
    assert "::geography" in sql
    assert "geography(GEOMETRY" not in sql
    assert "ST_MakePoint" in sql
    assert "ORDER BY" in sql
    assert "LIMIT" in sql


def test_search_statement_binds_coordinates() -> None:
    params = RestaurantSearchParams(lat=-23.5325, lon=-46.7939)
    compiled = build_search_statement(params).compile(
        dialect=postgresql.dialect()
    )

    assert -23.5325 in compiled.params.values()
    assert -46.7939 in compiled.params.values()
