#!/usr/bin/env python3
import re, sys, json

fail = False

# Backend
with open("backend/pyproject.toml") as f:
    m = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
be_version = m.group(1) if m else sys.exit("backend/pyproject.toml: version not found")

# Frontend
with open("frontend/package.json") as f:
    fe_version = json.load(f)["version"]

for version, changelog, label in [
    (be_version, "backend/CHANGELOG.md", "backend"),
    (fe_version, "frontend/CHANGELOG.md", "frontend"),
]:
    with open(changelog) as f:
        if re.search(rf"^## \[{re.escape(version)}\]", f.read(), re.MULTILINE):
            print(f"✓ {label}: changelog has [{version}]")
        else:
            print(f"✗ {label}: changelog missing [{version}] section")
            fail = True

sys.exit(1 if fail else 0)
