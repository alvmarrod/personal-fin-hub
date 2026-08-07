#!/usr/bin/env python3
"""Regenerate shields.io coverage badge from backend pytest coverage data."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

BADGES_DIR = Path(__file__).resolve().parent
REPO_ROOT = BADGES_DIR.parent
BACKEND = REPO_ROOT / "backend"


def _color_for_pct(pct: float) -> str:
    if pct >= 90:
        return "brightgreen"
    if pct >= 80:
        return "green"
    if pct >= 70:
        return "yellowgreen"
    if pct >= 60:
        return "yellow"
    if pct >= 50:
        return "orange"
    return "red"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    cov_path = BACKEND / "coverage.json"

    if args.skip_tests:
        if not cov_path.exists():
            print("coverage.json not found and --skip-tests specified", flush=True)
            return
    else:
        result = subprocess.run(
            [
                "uv", "run", "pytest",
                "--cov=services", "--cov=routes", "--cov=models",
                "--cov=scheduler", "--cov=db",
                "--cov-report=json", "--cov-report=",
                "-q",
            ],
            capture_output=True, text=True, cwd=BACKEND,
        )
        if result.returncode != 0:
            print(f"pytest failed with rc={result.returncode}")
            print(result.stdout)
            print(result.stderr, flush=True)
            return

    if not cov_path.exists():
        print("coverage.json not found")
        return

    with open(cov_path) as f:
        data = json.load(f)
    totals = data["totals"]
    pct = totals["percent_covered"]
    covered = totals["covered_lines"]
    total = totals["num_statements"]

    badge = {
        "schemaVersion": 1,
        "label": "backend coverage",
        "message": f"{pct:.1f}%",
        "color": _color_for_pct(pct),
    }

    (BADGES_DIR / "coverage.json").write_text(json.dumps(badge, indent=2) + "\n")
    print(f"Badge updated: {pct:.1f}% ({covered}/{total})")
    if not args.skip_tests:
        cov_path.unlink()


if __name__ == "__main__":
    main()
