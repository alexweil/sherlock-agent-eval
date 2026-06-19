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


def band_for(score: int, bands) -> str:
    """Pick a band label for `score`. `bands` is a list of [max, label] pairs
    (a null/None max is the open-ended top band). Returns "" if none match."""
    for cap, label in bands or []:
        if cap is None or score <= cap:
            return label
    return ""


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

    # Optional, per-case: a reference ("par") score to compare against and the
    # comparison bands. Both live in case.json meta.scoring. If absent, the scorer
    # reports only the raw final score — it never invents an absolute 100-point scale.
    scoring = case["meta"].get("scoring") or {}
    ref = scoring.get("reference_score")
    ref_label = scoring.get("reference_label", "reference")
    band = band_for(final, scoring.get("bands"))

    detail = "\n".join(f"  - Question {k}: {v} pts" for k, v in grades.items())
    final_line = f"## Final score: **{final} pts**"
    if ref is not None:
        final_line += f" ({ref_label}: {ref})"
    if band:
        final_line += f"\n  Band: {band}"

    text = f"""# Game result — {case['meta']['title']}

## Answers
{detail}

  **Answer subtotal: {points} pts**

## Clues
  - Clues followed (net): {net_clues}{f" (discounted {len(discounted)} free)" if discounted else ""}
  - Holmes's clues: {holmes['clues']}
  - Adjustment: 5 × ({holmes['clues']} − {net_clues}) = {5 * delta:+d} pts
  - Counted route: {', '.join(counted) or '(none)'}

{final_line}

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
