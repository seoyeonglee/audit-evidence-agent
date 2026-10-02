from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text

from .models import metadata


class Store:
    def __init__(self, url: str):
        self.url = url
        sqlite = url.startswith("sqlite")
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            **(
                {"connect_args": {"check_same_thread": False, "timeout": 30}}
                if sqlite
                else {"pool_size": 5, "max_overflow": 5}
            ),
        )
        if sqlite:

            @event.listens_for(self.engine, "connect")
            def configure(dbapi_connection, _):
                dbapi_connection.execute("PRAGMA foreign_keys=ON")
                dbapi_connection.execute("PRAGMA journal_mode=WAL")
                dbapi_connection.execute("PRAGMA busy_timeout=30000")

    @contextmanager
    def transaction(self, tenant_id: str | None = None):
        with self.engine.connect() as conn:
            if self.engine.dialect.name == "sqlite":
                # Serialize mutations across processes, not just Python threads.
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                conn.begin()
                conn.execute(
                    text("SELECT set_config('app.tenant_id', :tenant, true)"),
                    {"tenant": tenant_id or ""},
                )
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def migrate(self):
        """Bootstrap schema with migration credentials, never runtime credentials."""
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            if self.engine.dialect.name == "sqlite":
                for verb in ["UPDATE", "DELETE"]:
                    conn.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS audit_no_{verb.lower()}
                    BEFORE {verb} ON audit_events BEGIN
                    SELECT RAISE(ABORT, 'audit events are append-only'); END""")
            else:
                sql = (
                    Path(__file__).resolve().parents[2]
                    / "infrastructure/postgres/security.sql"
                )
                conn.execute(text(sql.read_text()))
