"""
Параметры подключения к БД из окружения (.env, переменные в Docker/хостинге)
и при необходимости из Streamlit Secrets (прод на Streamlit Cloud).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_project_root() / ".env")
    except ImportError:
        pass


_load_dotenv()


def _from_streamlit_secrets(name: str) -> str | None:
    try:
        import streamlit as st

        if not hasattr(st, "secrets") or name not in st.secrets:
            return None
        return str(st.secrets[name])
    except Exception:
        return None


def _get_env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val not in (None, ""):
        return val
    from_st = _from_streamlit_secrets(name)
    if from_st not in (None, ""):
        return from_st
    return default


@lru_cache(maxsize=1)
def get_database_settings() -> dict[str, str]:
    host = _get_env("DB_HOST", "localhost") or "localhost"
    port = _get_env("DB_PORT", "5432") or "5432"
    dbname = _get_env("DB_NAME", "football_service") or "football_service"
    user = _get_env("DB_USER", "postgres") or "postgres"
    password = _get_env("DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "Не задан пароль к БД (DB_PASSWORD). Скопируйте .env.example в .env "
            "и заполните переменные, либо задайте секреты на хостинге (см. README)."
        )
    sslmode = _get_env("DB_SSLMODE") or ""
    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
        "sslmode": sslmode,
    }
