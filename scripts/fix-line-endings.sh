#!/usr/bin/env bash
# Force LF line endings on every staged text file.
#
# pre-commit's `mixed-line-ending --fix=lf` only rewrites files whose line
# endings are MIXED (some LF, some CRLF). A file that is entirely CRLF is not
# treated as mixed, so it slips through unchanged. This hook normalizes ALL
# staged text files to LF and fails the commit when it changes one, so the
# change appears in the diff and must be staged to proceed.
set -euo pipefail

status=0
for f in "$@"; do
  [ -f "$f" ] || continue

  # Skip binary files. `grep -I` treats files containing NUL bytes as binary
  # and reports no match, so databases and images are never touched.
  grep -Iq . "$f" 2>/dev/null || continue

  # Any carriage return means the file uses (uniform or mixed) CRLF. Collapse
  # each CRLF pair, then turn any residual lone CR into LF so no carriage
  # return survives (a CR not followed by LF is otherwise left behind).
  if grep -q "$(printf '\r')" "$f" 2>/dev/null; then
    perl -0pi -e 's/\r\n/\n/g; s/\r/\n/g' "$f"
    echo "normalized to LF: $f"
    status=1
  fi
done
exit "$status"