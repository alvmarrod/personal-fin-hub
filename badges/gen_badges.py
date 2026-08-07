#!/usr/bin/env python3
"""Regenerate shields.io badge JSON files from backend coverage data."""

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
    passed = 0
    skipped = 0

    if args.skip_tests:
        if not cov_path.exists():
            print("coverage.json not found and --skip-tests specified", flush=True)
            return
        passed = -1
        skipped = -1
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

        for line in result.stdout.splitlines():
            if "passed" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "passed," and i > 0:
                        passed = int(parts[i - 1])
                    elif p == "skipped," and i > 0:
                        skipped = int(parts[i - 1])

    if not cov_path.exists():
        print("coverage.json not found")
        return

    with open(cov_path) as f:
        data = json.load(f)
    totals = data["totals"]
    pct = totals["percent_covered"]
    covered = totals["covered_lines"]
    total = totals["num_statements"]

    coverage_badge = {
        "schemaVersion": 1,
        "label": "backend coverage",
        "message": f"{pct:.1f}%",
        "color": _color_for_pct(pct),
    }

    tests_msg = f"{passed} passed" if passed >= 0 else "test suite"
    if skipped > 0:
        tests_msg += f", {skipped} skipped"

    tests_badge = {
        "schemaVersion": 1,
        "label": "backend tests",
        "message": tests_msg,
        "color": "brightgreen" if passed > 0 else "lightgrey",
    }

    (BADGES_DIR / "coverage.json").write_text(json.dumps(coverage_badge, indent=2) + "\n")
    (BADGES_DIR / "tests.json").write_text(json.dumps(tests_badge, indent=2) + "\n")

    print(f"Badges updated: coverage {pct:.1f}% ({covered}/{total}), {tests_msg}")
    if not args.skip_tests:
        cov_path.unlink()


if __name__ == "__main__":
    main()
