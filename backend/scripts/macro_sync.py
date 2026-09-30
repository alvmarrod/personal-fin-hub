"""On-demand macro data source sync. Run from the backend dir:

uv run python -m scripts.macro_sync [--slug SLUG ...]

With no ``--slug``, syncs every Wired series (respecting the freshness skip).
Pass one or more ``--slug`` to force a specific series.
"""

import argparse
import sys

from services.macro_sync_svc import sync_series


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync raw macro series into the database")
    parser.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        help="series slug to sync (repeatable); default: all Wired series",
    )
    args = parser.parse_args()

    result = sync_series(args.slugs)

    if result.get("busy"):
        print("macro sync already running", file=sys.stderr)
        return 1

    for item in result.get("series", []):
        if item.get("error"):
            print(f"{item['slug']}: error: {item['error']}")
        elif item.get("skipped"):
            print(f"{item['slug']}: skipped ({item['skipped']})")
        else:
            print(f"{item['slug']}: +{item['added']} observations")

    print(f"total added: {result.get('total_added', 0)}")
    if result.get("circuit_open"):
        print("note: a provider circuit is open", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
