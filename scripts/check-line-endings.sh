#!/usr/bin/env bash
# Scan the repository's canonical text content for carriage returns.
#
# `.gitattributes eol=lf` converts CRLF to LF on checkout, so the working tree
# can look LF-clean even when a committed blob still carries CR bytes. This
# guard reads the canonical store (git rev or the index) instead of the
# working tree, so a CRLF blob is found even when the worktree masks it.
#
# Usage:
#   scripts/check-line-endings.sh          # scan HEAD (committed content)
#   scripts/check-line-endings.sh --staged # scan the index (pre-commit)
#
# `git grep -I` skips binary files (those containing NUL bytes), so databases
# and images are never flagged.
set -euo pipefail

if [ "${1:-}" = "--staged" ]; then
  target="--cached"
  why="index (what this commit is about to record)"
else
  target="HEAD"
  why="HEAD (committed content)"
fi

files=$(git grep -I -l -e "$(printf '\r')" "$target" -- ':!backend/config.json' 2>/dev/null || true)

if [ -n "$files" ]; then
  echo "CR byte(s) found in text content under $why:" >&2
  echo "$files" >&2
  echo "Convert these to LF before committing." >&2
  exit 1
fi

exit 0