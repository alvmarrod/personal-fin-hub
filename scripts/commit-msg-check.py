#!/usr/bin/env python3
"""Validate commit messages follow conventional format: type(scope): description"""
import re, sys

TYPES = "feat|fix|chore|docs|refactor|test|style|perf|ci|build"

with open(sys.argv[1]) as f:
    line = f.readline().strip()

# Allow merge commits
if line.startswith("Merge "):
    sys.exit(0)

if re.match(rf"^({TYPES})(\([^)]+\))?: .+", line):
    sys.exit(0)

print(f"✗ invalid commit message: {line}")
print(f"  format: type(scope): description")
print(f"  types: {TYPES.replace('|', ', ')}")
sys.exit(1)
