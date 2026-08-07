#!/usr/bin/env python3
"""Extract release notes from both changelogs for a given version."""
import re, sys

version = sys.argv[1]
body = []

for path, label in [("backend/CHANGELOG.md", "Backend"), ("frontend/CHANGELOG.md", "Frontend")]:
    with open(path) as f:
        text = f.read()

    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[)", text, re.MULTILINE | re.DOTALL)
    if m:
        section = m.group(1).strip()
        body.append(f"## {label}\n\n{section}")

if not body:
    sys.exit(f"version [{version}] not found in changelogs")

print("\n\n".join(body))
