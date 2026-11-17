"""
Ubicity Core Engine components -- keeping it agnostic of the Flask
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Iterator, Optional

import importlib
import re
from contextlib import contextmanager

# SQLAlchemy event support, used to set SQLite PRAGMAs on connect.
import sqlite3
import sqlalchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (DeclarativeBase, declared_attr, has_inherited_table,
                            scoped_session, sessionmaker)
from sqlalchemy.pool import StaticPool

# The Engine components:

# 1. Database. The models and the code that uses them see 'db', which
# exposes the part of the Flask-SQLAlchemy API this code uses --
# db.Model, db.session, db.Column and the other column types,
# db.relationship, db.create_all() -- over plain SQLAlchemy, so none of
# it needs Flask. There is one session, thread-scoped; whoever owns a
# unit of work removes it when done (the Flask app does so at the end of
# each app context, session_scope() at the end of its block).

session: scoped_session = scoped_session(sessionmaker())


class Base(DeclarativeBase):
    # The models declare columns as db.Column(...) without Mapped[]
    # annotations, the style Flask-SQLAlchemy's base accepted
    __allow_unmapped__ = True

    # Model.query, as Flask-SQLAlchemy provided it
    query = session.query_property()

    @declared_attr.directive
    def __tablename__(cls) -> Optional[str]:
        """The table names Flask-SQLAlchemy generated: a model at the
        root of a hierarchy gets its class name in snake_case, and a
        subclass that names no table of its own shares its parent's
        (single-table inheritance). A __tablename__ in the class wins.
        """
        if has_inherited_table(cls):
            return None
        name = re.sub(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))", r"_\1", cls.__name__)
        return name.lower().lstrip("_")

    def __repr__(self) -> str:
        # Flask-SQLAlchemy's repr, which messages and output rely on
        state = sqlalchemy.inspect(self)
        if state.transient:
            pk = f"(transient {id(self)})"
        elif state.pending:
            pk = f"(pending {id(self)})"
        else:
            pk = ", ".join(map(str, state.identity))
        return f"<{type(self).__name__} {pk}>"


class _DB:
    """Flask-free stand-in for the Flask-SQLAlchemy object"""

    Model = Base
    metadata = Base.metadata
    session = session

    Column = sqlalchemy.Column
    ForeignKey = sqlalchemy.ForeignKey
    Index = sqlalchemy.Index
    Integer = sqlalchemy.Integer
    String = sqlalchemy.String
    Boolean = sqlalchemy.Boolean
    Enum = sqlalchemy.Enum
    DateTime = sqlalchemy.DateTime
    PickleType = sqlalchemy.PickleType
    relationship = staticmethod(sqlalchemy.orm.relationship)

    def create_all(self) -> None:
        """Create the tables of every model imported so far"""
        Base.metadata.create_all(session.get_bind())


db: _DB = _DB()

_engine: Optional[Engine] = None


def init_db(db_uri: str) -> Engine:
    """Bind the session to the database at 'db_uri' and import every
    model module so the mappers can resolve their relationships.

    Calling it again with the same URI reuses the engine; with another
    URI it replaces it.
    """
    global _engine
    if _engine is None or str(_engine.url) != str(sqlalchemy.engine.make_url(db_uri)):
        session.remove()
        if _engine is not None:
            _engine.dispose()
        _engine = sqlalchemy.create_engine(db_uri, **_engine_options(db_uri))
        session.configure(bind=_engine)
        # Types cached from the previous database are not in this one
        from tosca_core.models import builtin_types
        builtin_types.reset()

    from tosca_core.constants import constants
    for model_module in constants.MODEL_MODULES:
        importlib.import_module(model_module)
    return _engine


def _engine_options(db_uri: str) -> dict[str, Any]:
    """An in-memory SQLite database lives in its connection, so every
    thread must share one (the default Flask-SQLAlchemy applied)"""
    url = sqlalchemy.engine.make_url(db_uri)
    if url.get_backend_name() == "sqlite" and url.database in (None, "", ":memory:"):
        return {"poolclass": StaticPool,
                "connect_args": {"check_same_thread": False}}
    return {}


def reset_session() -> None:
    """Return the ORM to a clean slate: roll back, discard the session,
    and forget the built-in types cached from it.

    Call it between units of work when one may have failed, as a batch
    validator does between targets. A failed flush can leave objects
    detached that the identity map would otherwise keep handing out, and
    rolling back alone does not discard them.
    """
    try:
        session.rollback()
    except Exception:
        # A session broken by a failed flush may refuse even this; the
        # remove() below discards it regardless
        pass
    finally:
        session.remove()
        from tosca_core.models import builtin_types
        builtin_types.reset()


@contextmanager
def session_scope() -> Iterator[scoped_session]:
    """A unit of work: commit on success, roll back on error, and
    remove the session either way"""
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.remove()


# When DB_URI points at SQLite, set sensible per-connection PRAGMAs: WAL
# journaling + a busy timeout (so a momentarily-locked database waits rather
# than raising "database is locked"), and foreign-key enforcement (off by
# default in SQLite). No-op on PostgreSQL -- the isinstance() check skips any
# non-sqlite3 DBAPI connection (e.g. psycopg2). Registered on the generic
# Engine class, so it also covers a future standalone validator's SQLite.
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection: object, connection_record: object) -> None:
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
