"""Tests for db/session.py — engine, SessionLocal, and get_db dependency."""

from sqlalchemy.orm import Session

from backend.db.session import SessionLocal, engine, get_db


def test_engine_connects() -> None:
    with engine.connect() as conn:
        result = conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        assert result.scalar() == 1


def test_session_local_yields_session() -> None:
    session = SessionLocal()
    assert isinstance(session, Session)
    session.close()


def test_get_db_yields_and_closes() -> None:
    gen = get_db()
    session = next(gen)
    assert isinstance(session, Session)
    try:
        next(gen)
    except StopIteration:
        pass
