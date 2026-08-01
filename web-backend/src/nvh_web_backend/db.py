"""Per-request DB session dependency, reading the session factory that
app.py's create_app() builds once and stores on app.state -- the standard
FastAPI Depends()+generator pattern, nothing exotic needed since there's no
auth/multi-tenancy here."""

from __future__ import annotations

from typing import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
