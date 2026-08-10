import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


def run_with_temp_migration(conn, name: str, content: str):
    """Run ``_run_migrations`` with a temporary migration module present.

    The temp module lives in db/migrations/ so the runner picks it up, and is
    removed (along with any import cache entry) afterwards.
    """
    from db.connection import _run_migrations

    path = MIGRATIONS_DIR / f"{name}.py"
    try:
        path.write_text(content)
        sys.modules.pop(f"db.migrations.{name}", None)
        _run_migrations(conn)
    finally:
        path.unlink(missing_ok=True)
        sys.modules.pop(f"db.migrations.{name}", None)
