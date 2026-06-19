#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic helper for the MONOLITH topologies (single agent).

A monolith is one agent that BOTH explores and reasons, using the workspace and
`./gm` directly with `prompts/player.md`. Three variants from the article:

  - baseline / methodical: the agent keeps conversation memory across turns; it
    needs no helper — just the workspace, `./gm`, and the prompt.
  - clean-context: the agent is re-spawned FRESH each turn, with no conversation
    memory. Its only memory is `notes.md` (which it rewrites each turn) plus
    `served-clues.md` (the verbatim clues it has followed). This helper
    regenerates `served-clues.md` from the log before each fresh spawn.

This script invokes NO LLMs.

  served <run>    (Re)compile served-clues.md into the run's workspace, so a
                  freshly-spawned clean-context monolith can recover its clue
                  memory. Run it before each turn of a clean-context run.

Usage:
    python drivers/monolith.py served runs/r1
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dupla import compile_served  # noqa: E402  (shared with the duo driver)


def served(run: Path):
    ws = run / "workspace"
    if not ws.exists():
        sys.exit(f"[mono] No workspace in {run}")
    out = ws / "served-clues.md"
    out.write_text(compile_served(run / "log.jsonl"), encoding="utf-8")
    n = out.read_text(encoding="utf-8").count("\n---\n")
    print(f"[mono] served-clues.md (~{n} verbatim clues) → {out}")
    print("[mono] The clean-context monolith reads notes.md + served-clues.md each fresh turn.")


def main():
    argv = sys.argv[1:]
    if len(argv) < 2 or argv[0] != "served":
        sys.exit(__doc__)
    run = Path(argv[1]).resolve()
    if not run.exists():
        sys.exit(f"[mono] No such run: {run}")
    served(run)


if __name__ == "__main__":
    main()
