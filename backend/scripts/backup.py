"""On-demand database backup. Run from the backend dir:

uv run python -m scripts.backup [--tag NAME]
"""

import argparse
import sys

from services.backup_svc import (
    BackupError,
    backup_dir,
    backup_retention,
    create_backup,
    prune_backups,
    verify_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a verified backup of the database")
    parser.add_argument("--tag", default="manual", help="label logged with the backup (default: manual)")
    args = parser.parse_args()

    try:
        path = create_backup(args.tag)
    except BackupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    ok = verify_backup(path)
    print(f"backup: {path}")
    print(f"verified: {'yes' if ok else 'NO'}")
    print(f"size: {path.stat().st_size} bytes")
    print(f"dir: {backup_dir()}")

    pruned = prune_backups()
    if pruned:
        print(f"pruned {len(pruned)} old backup(s) (retention={backup_retention()})")
    else:
        print(f"retention: {backup_retention()} (nothing pruned)")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
