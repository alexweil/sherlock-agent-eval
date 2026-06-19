#!/bin/sh
# Leakage audit for the public repo.
#
# Greps the harness (code, prompts, schema, toy case, README) against a PRIVATE
# denylist of case strings — character names, real addresses, the real case title,
# document ids, etc. The denylist itself is the leak if committed, so it MUST live
# OUTSIDE this repo and is never checked in (see .gitignore / README).
#
# Usage:  ./scripts/leakcheck.sh /path/to/private-denylist.txt
# Denylist format: one term (or regex) per line; blank lines and #-comments ok.
#
# Exit 0 = clean (no matches). Exit 1 = potential leak found. Exit 2 = usage error.
#
# docs/ (the published, paraphrased article) is excluded on purpose: it names the
# game and its publisher by design. Audit it by eye, not with this denylist.

set -eu

DENYLIST="${1:-}"
if [ -z "$DENYLIST" ] || [ ! -f "$DENYLIST" ]; then
  echo "usage: $0 /path/to/private-denylist.txt   (kept OUTSIDE this repo)" >&2
  exit 2
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required: https://github.com/BurntSushi/ripgrep" >&2
  exit 2
fi

echo "Auditing $REPO against $DENYLIST (excluding docs/, .git/)..."
# -w (word boundaries) so denylisted names don't match as substrings of unrelated
# words (e.g. a name 'Gran' inside 'granting'). Keep denylist entries word-level.
if rg -i -w --hidden \
      --glob '!.git' \
      --glob '!docs/**' \
      --glob '!scripts/leakcheck.sh' \
      -f "$DENYLIST" "$REPO"; then
  echo
  echo "POTENTIAL LEAK: the matches above are denylisted case strings. Fix before publishing." >&2
  exit 1
else
  echo "Clean: no denylisted case strings found in the harness."
fi
