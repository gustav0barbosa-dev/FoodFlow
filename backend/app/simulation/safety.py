"""Guardas de segurança para scripts que escrevem dados de simulação.

Regras (aplicadas por ``guard_write``):

- o banco de destino é sempre impresso antes da operação;
- ``--dry-run`` não exige ``--yes`` e não grava nada;
- sem ``--yes`` o script aborta;
- bancos de produção (ambiente ou nome do banco) são bloqueados;
- hosts remotos exigem ``--allow-remote-db`` explícito.

O bloqueio é intencionalmente conservador: dados sintéticos nunca devem
contaminar um banco com usuários reais.
"""

from __future__ import annotations

import argparse
import os
from urllib.parse import urlparse

from app.core.config import settings

PRODUCTION_ENV_VALUES = {"production", "prod"}
PRODUCTION_DB_MARKERS = ("prod", "production")
LOCAL_HOSTS = {
    "",
    "localhost",
    "127.0.0.1",
    "::1",
    "db",
    "postgres",
    "host.docker.internal",
}


def database_label(url: str | None = None) -> str:
    """Rótulo legível do banco, sem expor usuário/senha."""
    raw = (url or settings.database_url)
    raw = raw.replace("+asyncpg", "").replace("+psycopg2", "")
    parsed = urlparse(raw)
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.hostname or '?'}{port}{parsed.path or ''}"


def environment_name() -> str:
    return (
        os.getenv("FOODFLOW_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or "development"
    ).strip().lower()


def _parsed_url(url: str | None = None):
    raw = (url or settings.database_url)
    raw = raw.replace("+asyncpg", "").replace("+psycopg2", "")
    return urlparse(raw)


def production_reason(url: str | None = None) -> str | None:
    """Motivo pelo qual o banco parece ser de produção (ou ``None``)."""
    env = environment_name()
    if env in PRODUCTION_ENV_VALUES:
        return f"ambiente '{env}' (FOODFLOW_ENV/APP_ENV/ENVIRONMENT)"

    parsed = _parsed_url(url)
    db_name = (parsed.path or "").lstrip("/").lower()
    if any(marker in db_name for marker in PRODUCTION_DB_MARKERS):
        return f"nome do banco '{db_name}' contém marcador de produção"

    host = (parsed.hostname or "").lower()
    return None


def remote_host_reason(url: str | None = None) -> str | None:
    host = (_parsed_url(url).hostname or "").lower()
    if host not in LOCAL_HOSTS:
        return f"host remoto '{host}'"
    return None


def guard_write(args: argparse.Namespace, *, url: str | None = None) -> None:
    """Valida o destino antes de qualquer escrita.

    ``--dry-run`` retorna sem exigir confirmação. Para escrita real, o banco de
    produção é bloqueado antes do pedido de ``--yes``.
    """
    label = database_label(url)
    print(f"Banco de destino: {label}")

    if getattr(args, "dry_run", False):
        print("--dry-run: nenhuma alteração será gravada.")
        return

    reason = production_reason(url)
    if reason:
        print(
            f"BLOQUEADO: {reason}. Scripts de simulação não escrevem em produção.\n"
            "Use um banco separado (ex.: DATABASE_URL=.../foodflow_sim)."
        )
        raise SystemExit(3)

    remote = remote_host_reason(url)
    if remote and not getattr(args, "allow_remote_db", False):
        print(
            f"BLOQUEADO: {remote}. Se for um banco de simulação remoto, "
            "repita com --allow-remote-db."
        )
        raise SystemExit(3)

    if not getattr(args, "yes", False):
        print(
            "Este comando escreve no banco. Revise o destino e repita com --yes "
            "(ou use --dry-run)."
        )
        raise SystemExit(2)
