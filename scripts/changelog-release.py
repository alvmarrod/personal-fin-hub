#!/usr/bin/env python3
"""Extract release notes from changelogs for a given version.

Usage:
    python3 scripts/changelog-release.py 0.6.0          # both sides
    python3 scripts/changelog-release.py 0.6.1 frontend  # frontend only
    python3 scripts/changelog-release.py 0.6.0 backend   # backend only
"""
import re
import sys

version = sys.argv[1]
filter_side = sys.argv[2] if len(sys.argv) > 2 else None
body = []

for path, label in [("backend/CHANGELOG.md", "Backend"), ("frontend/CHANGELOG.md", "Frontend")]:
    if filter_side and filter_side != label.lower():
        continue
    with open(path) as f:
        text = f.read()

    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[)", text, re.MULTILINE | re.DOTALL)
    if m:
        section = m.group(1).strip()
        body.append(f"## {label}\n\n{section}")

if not body:
    sides = filter_side or "either changelog"
    sys.exit(f"version [{version}] not found in {sides}")

print("\n\n".join(body))
