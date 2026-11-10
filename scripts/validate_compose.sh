#!/usr/bin/env bash
# Valida o Docker Compose do FoodFlow de ponta a ponta.
#
# Requisitos: Docker com Compose v2, curl e python3.
#
# O script:
#   1. valida a configuração dos Compose de desenvolvimento e produção;
#   2. sobe a stack de desenvolvimento e confere migrate, PostGIS, Redis,
#      seed, /health, /ready, busca geoespacial e /recommendations;
#   3. sobe a stack de produção e confere o volume persistente
#      `backend_models` montado em /app/models.
#
# Uso:
#   bash scripts/validate_compose.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Nome de projeto isolado: a validação não mexe no ambiente do usuário.
PROJECT_NAME="foodflow_compose_validation"
COMPOSE=(docker compose -p "$PROJECT_NAME")
PROD_COMPOSE=(docker compose -p "$PROJECT_NAME" -f docker-compose.yml -f docker-compose.prod.yml)
USER_ID="a54a52c3-8543-56d3-8e4b-6d8220667bd5"
TMP_DIR="${TMPDIR:-/tmp}"

cleanup() {
  # O projeto é isolado (nome próprio), então remover os volumes não afeta
  # o ambiente de desenvolvimento do usuário.
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  "${PROD_COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  echo "ERRO: $*" >&2
  exit 1
}

show_logs_on_error() {
  local -a compose=("$@")
  "${compose[@]}" ps || true
  "${compose[@]}" logs --no-color || true
}

if ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose v2 não está disponível."
fi

echo "==> Validando arquivos Compose"
"${COMPOSE[@]}" config >/dev/null
"${PROD_COMPOSE[@]}" config >/dev/null
"${PROD_COMPOSE[@]}" config | grep -q "backend_models" \
  || fail "volume backend_models ausente no Compose de produção."

wait_for_ready() {
  local attempts=60
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS http://localhost:8000/ready >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

validate_postgres_redis_seed() {
  local -a compose=("$@")

  echo "--- PostGIS"
  local postgis
  postgis="$("${compose[@]}" exec -T postgres psql -U foodflow -d foodflow -tAc \
    "SELECT extname FROM pg_extension WHERE extname='postgis';" | tr -d '\r[:space:]')"
  [ "$postgis" = "postgis" ] || fail "extensão PostGIS não encontrada."
  "${compose[@]}" exec -T postgres psql -U foodflow -d foodflow -tAc \
    "SELECT PostGIS_Version();"

  echo "--- Migrações Alembic"
  local version
  version="$("${compose[@]}" exec -T postgres psql -U foodflow -d foodflow -tAc \
    "SELECT version_num FROM alembic_version;" | tr -d '\r[:space:]')"
  [ -n "$version" ] || fail "alembic_version vazio (migrate não aplicou o schema)."
  echo "versão aplicada: $version"

  echo "--- Seed"
  local counts
  counts="$("${compose[@]}" exec -T postgres psql -U foodflow -d foodflow -tAc \
    "SELECT (SELECT count(*) FROM restaurants), (SELECT count(*) FROM users), (SELECT count(*) FROM orders);" \
    | tr -d '\r')"
  echo "restaurantes/usuários/pedidos: $counts"
  local restaurants
  restaurants="$(echo "$counts" | awk -F'|' '{print $1}' | tr -d '[:space:]')"
  [ "${restaurants:-0}" -ge 1 ] || fail "seed não populou restaurantes."

  echo "--- Redis"
  local pong
  pong="$("${compose[@]}" exec -T redis redis-cli ping | tr -d '\r[:space:]')"
  [ "$pong" = "PONG" ] || fail "Redis não respondeu PONG."
}

validate_api() {
  echo "--- /health e /ready"
  curl -fsS http://localhost:8000/health >"$TMP_DIR/foodflow_health.json"
  curl -fsS http://localhost:8000/ready >"$TMP_DIR/foodflow_ready.json"
  cat "$TMP_DIR/foodflow_health.json"
  cat "$TMP_DIR/foodflow_ready.json"
  grep -Eq '"database"[: ]*true' "$TMP_DIR/foodflow_ready.json" \
    || fail "/ready não reportou database=true."

  echo "--- Busca geoespacial"
  curl -fsS "http://localhost:8000/api/v1/restaurants/search?lat=-23.5325&lon=-46.7939&radius_km=50" \
    >"$TMP_DIR/foodflow_search.json"
  python3 - "$TMP_DIR/foodflow_search.json" <<'PY'
import json
import sys

items = json.load(open(sys.argv[1], encoding="utf-8"))
assert isinstance(items, list) and items, "busca geoespacial retornou vazio"
assert all("distance_km" in item for item in items), "distance_km ausente"
print(f"busca geoespacial: {len(items)} restaurantes")
PY

  echo "--- Recomendações personalizadas"
  curl -fsS "http://localhost:8000/api/v1/recommendations?user_id=${USER_ID}&lat=-23.5325&lon=-46.7939&turno=tarde" \
    >"$TMP_DIR/foodflow_recommendations.json"
  python3 - "$TMP_DIR/foodflow_recommendations.json" <<'PY'
import json
import sys

items = json.load(open(sys.argv[1], encoding="utf-8"))
assert isinstance(items, list) and items, "recommendations retornou vazio"
assert all("score" in item for item in items), "score ausente nas recomendações"
scores = [item["score"] for item in items]
assert scores == sorted(scores, reverse=True), "recomendações fora de ordem"
print(f"recomendações: {len(items)} itens, top score={scores[0]}")
PY
}

echo "==> Subindo stack de desenvolvimento"
"${COMPOSE[@]}" up -d --build
"${COMPOSE[@]}" wait migrate || { show_logs_on_error "${COMPOSE[@]}"; fail "serviço migrate falhou."; }
wait_for_ready || { show_logs_on_error "${COMPOSE[@]}"; fail "backend não ficou pronto."; }
validate_postgres_redis_seed "${COMPOSE[@]}"
validate_api
"${COMPOSE[@]}" exec -T backend sh -c 'test -d /app/models' \
  || fail "diretório /app/models ausente no backend."
echo "backend_models (dev): usando ./backend/models"

echo "==> Derrubando stack de desenvolvimento"
"${COMPOSE[@]}" down -v --remove-orphans

echo "==> Subindo stack de produção"
"${PROD_COMPOSE[@]}" up -d --build
"${PROD_COMPOSE[@]}" wait migrate || { show_logs_on_error "${PROD_COMPOSE[@]}"; fail "migrate de produção falhou."; }
wait_for_ready || { show_logs_on_error "${PROD_COMPOSE[@]}"; fail "backend de produção não ficou pronto."; }
validate_postgres_redis_seed "${PROD_COMPOSE[@]}"
validate_api
"${PROD_COMPOSE[@]}" exec -T backend python -c \
  'from pathlib import Path; assert Path("/app/models").is_dir(); print("/app/models montado")' \
  || fail "volume backend_models não está montado em /app/models."
"${PROD_COMPOSE[@]}" exec -T backend sh -c \
  'echo ok > /app/models/.volume_check' \
  || fail "volume backend_models não é gravável."
"${PROD_COMPOSE[@]}" exec -T backend sh -c \
  'test "$(cat /app/models/.volume_check)" = ok' \
  || fail "leitura do volume backend_models falhou."
"${PROD_COMPOSE[@]}" exec -T backend rm -f /app/models/.volume_check
docker volume inspect "${PROJECT_NAME}_backend_models" >/dev/null 2>&1 \
  || fail "volume nomeado ${PROJECT_NAME}_backend_models não existe."
"${PROD_COMPOSE[@]}" config | grep -q "backend_models" \
  || fail "volume backend_models ausente na configuração de produção."

echo "==> Compose validado com sucesso (dev + prod)."
