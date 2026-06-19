#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final scoring for a game.

Combines ``grades.json`` (per-question points from the validator/judge — the
only component that reads the solution), the GM's clue counter (``state.json``),
and the case's Holmes clue count (``case.json``). Writes ``<run>/result.md``.

    final = answer_points + 5 × (Holmes's clue count − your net clues)

Usage: python -m sherlock_eval score --run runs/<run>
"""
import json
import sys
from pathlib import Path


def band(p: int) -> str:
    if p <= 30:
        return "≤30 — even good investigators sometimes come up short."
    if p < 70:
        return "35–65 — you solved most of the case."
    if p < 100:
        return "70–95 — strong work; only Holmes would have found the gaps."
    return "100+ — you matched or beat the master at his own game."


def run_score(run: Path) -> str:
    state = json.loads((run / "state.json").read_text(encoding="utf-8"))
    case = json.loads((run / "case.json").read_text(encoding="utf-8"))
    grades = json.loads((run / "grades.json").read_text(encoding="utf-8"))

    holmes = case["meta"]["holmes"]
    free = set(holmes.get("free", []))
    counted = [v["addr"] for v in state["visits"] if v["counted"]]
    discounted = [a for a in counted if a in free]
    net_clues = len(counted) - len(discounted)

    points = sum(grades.values())
    delta = holmes["clues"] - net_clues
    final = points + 5 * delta

    detail = "\n".join(f"  - Question {k}: {v} pts" for k, v in grades.items())
    text = f"""# Game result — {case['meta']['title']}

## Answers
{detail}

  **Answer subtotal: {points} pts**

## Clues
  - Clues followed (net): {net_clues}{f" (discounted {len(discounted)} free)" if discounted else ""}
  - Holmes's clues: {holmes['clues']}
  - Adjustment: 5 × ({holmes['clues']} − {net_clues}) = {5 * delta:+d} pts
  - Counted route: {', '.join(counted) or '(none)'}

## Final score: **{final} pts** (Holmes: 100)
  Band: {band(final)}

  Questions mode: {state['mode']}
"""
    (run / "result.md").write_text(text, encoding="utf-8")
    return text


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    run = Path(argv[argv.index("--run") + 1]).resolve()
    print(run_score(run))


if __name__ == "__main__":
    main()
