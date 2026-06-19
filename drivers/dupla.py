#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic helper for the DUO topology (Theorist + Explorer).

The duo splits the investigation into two agents with isolated contexts:
  - EXPLORER (workspace + ./gm): resolves name→address, visits, relays GM output
    VERBATIM. Never concludes. Spawned fresh per request; recovers state from
    `./gm status` + notes.md.
  - THEORIST (no workspace): keeps the world-model, falsifies hypotheses, and
    directs the exploration. Does not see the questions until it closes
    (faithful mode). Spawned fresh per turn; its memory is the externalized
    ledger + the served clues from the log.
The conductor (the orchestrating session) is a verbatim pipe between them.

This script invokes NO LLMs. It does the mechanical, auditable plumbing:

  phase0 <run>          Build free-packet.md (the free material, verbatim) that the
                        Theorist ingests in Phase 0. The two directories are NOT
                        dumped: they are the Explorer's lookup service.
  served <run>          Compile served-clues.md: the verbatim text of every clue
                        served so far, from log.jsonl (the objective truth), deduped.
  theorist-input <run> [--prompt <path>]
                        Assemble theorist/input.md = PROMPT + free-packet + served-clues
                        + lookups + prior ledger (+ unresolved-entity report, if present)
                        + the turn instruction. This is the ONLY thing handed to the
                        Theorist (it has no filesystem).
  coverage <run>        Deterministic ADDRESS-level backstop for the naming-completeness
                        gate: addresses cited in served clues but never visited.
  verify <run>          List the log's content events to audit that the conductor
                        relayed verbatim (cross-check against the transcript).

Closing handshake: when the Theorist emits `CLOSE` (intent), the conductor asks the
EXPLORER for an `UNRESOLVED-REPORT`, saves it to <run>/unresolved-report.md, and
regenerates theorist-input (now in "stage-2 closing": the Theorist must dispatch
each entity before `CLOSE-FINAL`). Run `coverage` as a cross-check.

Usage:
    python drivers/dupla.py phase0 runs/r1
    python drivers/dupla.py theorist-input runs/r1
    python drivers/dupla.py coverage runs/r1
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT = REPO / "prompts" / "theorist.md"

# Free material the Theorist receives whole (verbatim) in Phase 0.
# directory-*.md are left OUT on purpose: they are an on-demand lookup service.
FREE_PACKET = [
    ("rules.md", "Rules of play (the economy: thinking is free, visiting costs)"),
    ("intro.md", "Case introduction (the assignment)"),
    ("map.md", "The map: districts and the address system"),
    ("informants.md", "Recurring informants and their addresses"),
    ("newspaper.md", "The day's newspaper (ads and articles = case material)"),
]
CONTENT_EVENTS = {"visit", "decide", "index"}

FREE_HEADER = """# Free case material — Phase 0 packet (VERBATIM)

> You are the THEORIST. This is ALL the free, unlimited material of the case, as-is,
> handed to you before a single visit is spent. Names, ads, dates, and anomalies
> that are part of the mystery live here and cost nothing. Build your initial
> world-model and first hypotheses over this whole corpus.
>
> What is NOT here: the two directories (person→address, place→address). They are an
> index: ask the EXPLORER to resolve any name/category (`LOOKUP`) — it is free. PAID
> clues come from `VISIT` (the Explorer fetches them).
"""


def addr_re(run: Path):
    """Build the address regex from this run's case districts."""
    case = json.loads((run / "case.json").read_text(encoding="utf-8"))
    codes = sorted((d.upper() for d in case["meta"]["districts"]), key=len, reverse=True)
    return re.compile(r"\b(\d{1,3})\s+(" + "|".join(re.escape(c) for c in codes) + r")\b")


def phase0(run: Path):
    ws = run / "workspace"
    parts = [FREE_HEADER]
    for fname, desc in FREE_PACKET:
        p = ws / fname
        if not p.exists():
            sys.exit(f"[duo] Missing free material: {p}")
        body = p.read_text(encoding="utf-8").rstrip("\n")
        parts.append(f"\n\n{'=' * 78}\n## {desc}\n## (file: {fname}, verbatim)\n{'=' * 78}\n\n{body}")
    out = run / "free-packet.md"
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"[duo] free-packet.md built: {len(FREE_PACKET)} sections → {out}")


def compile_served(log_path: Path) -> str:
    seen, blocks = set(), []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("event") not in CONTENT_EVENTS:
                continue
            txt = (r.get("text") or "").strip()
            if not txt or txt in seen:
                continue
            seen.add(txt)
            blocks.append(txt)
    header = ("# Clues served so far (VERBATIM text, from log.jsonl)\n\n"
              "> Raw material: everything the Game Master served up to this point, as-is. "
              "The LAST is the most recent observation. Cross-check this against your ledger.\n")
    if not blocks:
        return header + "\n_(no clue has been visited yet)_\n"
    return header + "\n---\n\n" + "\n\n---\n\n".join(blocks) + "\n"


def served(run: Path):
    out = run / "served-clues.md"
    out.write_text(compile_served(run / "log.jsonl"), encoding="utf-8")
    n = out.read_text(encoding="utf-8").count("\n---\n")
    print(f"[duo] served-clues.md: ~{n} verbatim clues → {out}")


def theorist_input(run: Path, prompt_path: Path = DEFAULT_PROMPT):
    """Assemble the Theorist's full input for this turn."""
    free = (run / "free-packet.md")
    if not free.exists():
        sys.exit("[duo] Missing free-packet.md; run `phase0` first.")
    if not prompt_path.exists():
        sys.exit(f"[duo] No Theorist prompt at: {prompt_path}")
    served_md = compile_served(run / "log.jsonl")
    # The Theorist writes its ledger to theorist/ledger-out.md (its only write path);
    # fallback to a theorist-ledger.md the conductor may have saved on early turns.
    ledger = ""
    for lp in (run / "theorist" / "ledger-out.md", run / "theorist-ledger.md"):
        if lp.exists() and lp.read_text(encoding="utf-8").strip():
            ledger = lp.read_text(encoding="utf-8")
            break
    lookups_p = run / "lookups.md"
    lookups = lookups_p.read_text(encoding="utf-8") if lookups_p.exists() else ""
    report_p = run / "unresolved-report.md"
    report = report_p.read_text(encoding="utf-8") if report_p.exists() else ""
    is_first = not ledger.strip()
    closing = bool(report.strip())

    if is_first:
        instr = (
            "## YOUR TURN (Phase 0)\n\n"
            "This is the start. You have visited nothing. Study the free material above, "
            "build your **initial world-model** and hypotheses (labelling FACT/INFERENCE/"
            "SPECULATION with sources), list the **loose ends** (every anomaly that does not "
            "fit) and the **unresolved actors**, run the **falsification gate**, and end with "
            "ONE `ACTION:` line (see your role for the options).\n")
    elif closing:
        instr = (
            "## YOUR TURN — NAMING-COMPLETENESS GATE (closing, stage 2)\n\n"
            "You emitted `CLOSE`. The Explorer delivered the **unresolved-entity report** "
            "(section above). **Dispatch each item**: resolve it with a cheap lever (free "
            "`LOOKUP` — including the alias check: is it the cover name of someone you already "
            "saw? — or a `VISIT` if it is central and worth the cost) **or** declare it "
            "irrelevant/unreachable with an explicit reason. **Hard rule:** do NOT emit "
            "`CLOSE-FINAL` while any single item is BOTH unresolved AND has an untried FREE "
            "lever. Rewrite your ledger and end with ONE `ACTION:` line — the next lever, or "
            "`CLOSE-FINAL` (with per-item disposition) once everything is dispatched.\n")
    else:
        instr = (
            "## YOUR TURN\n\n"
            "Above you have (a) your **ledger from last turn** and (b) the **clues served "
            "verbatim** (the last is the newest observation you asked for). Integrate the new "
            "observation, **rewrite the ledger IN FULL** (it is your only memory next turn: "
            "include your reasoning and quote the decisive details verbatim, not just "
            "conclusions; keep the **unresolved actors** list), re-run the **falsification "
            "gate**, and end with ONE `ACTION:` line.\n")

    parts = [
        prompt_path.read_text(encoding="utf-8").rstrip("\n"),
        "\n\n" + "#" * 78 + "\n# FREE MATERIAL (Phase 0 — constant)\n" + "#" * 78 + "\n\n"
        + free.read_text(encoding="utf-8").rstrip("\n"),
        "\n\n" + "#" * 78 + "\n# CLUES SERVED SO FAR (verbatim)\n" + "#" * 78 + "\n\n"
        + served_md.rstrip("\n"),
    ]
    if lookups.strip():
        parts.append("\n\n" + "#" * 78 + "\n# LOOKUP RESULTS (free, not visits)\n"
                     + "#" * 78 + "\n\n" + lookups.rstrip("\n"))
    if not is_first:
        parts.append("\n\n" + "#" * 78 + "\n# YOUR LEDGER FROM LAST TURN\n" + "#" * 78
                     + "\n\n" + ledger.rstrip("\n"))
    if closing:
        parts.append("\n\n" + "#" * 78 + "\n# UNRESOLVED-ENTITY REPORT (from the Explorer)\n"
                     + "#" * 78 + "\n\n" + report.rstrip("\n"))
    parts.append("\n\n" + "#" * 78 + "\n" + instr + "#" * 78)

    tdir = run / "theorist"
    tdir.mkdir(exist_ok=True)
    out = tdir / "input.md"
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    tag = "PHASE 0" if is_first else ("CLOSING stage-2" if closing else "turn")
    print(f"[duo] {tag} ({prompt_path.name}): assembled → {out}")
    print("[duo] (the Theorist reads ONLY this file; clean dir, no case.json/state.json)")


def verify(run: Path):
    log = run / "log.jsonl"
    if not log.exists():
        sys.exit(f"[duo] No {log}")
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    content = [r for r in rows if r.get("event") in CONTENT_EVENTS or r.get("event") == "finalize"]
    print(f"[duo] {len(content)} content events in {run.name}:")
    for r in content:
        ev, args = r["event"], r.get("args")
        extra = f" · counted={r.get('counted')}" if ev == "visit" else ""
        print(f"  - [{ev}] {args}{extra} · {len(r.get('text') or '')} chars · clues={r['clues_followed']}")
    print("\n[duo] Cross-check these texts against served-clues.md and the Theorist transcript "
          "to confirm the conductor relayed verbatim.")


def coverage(run: Path):
    """Deterministic ADDRESS-level backstop: addresses cited in served clues that were
    never visited. Does NOT detect unnamed entities (that is the Explorer's
    UNRESOLVED-REPORT, which is authoritative); it only cross-checks map addresses."""
    log = run / "log.jsonl"
    if not log.exists():
        sys.exit(f"[duo] No {log}")
    rx = addr_re(run)
    visited, mentioned = set(), {}
    for line in log.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        ev = r.get("event")
        if ev == "visit" and isinstance(r.get("args"), str):
            visited.add(r["args"])
        if ev in CONTENT_EVENTS:
            for num, dist in rx.findall(r.get("text") or ""):
                mentioned.setdefault(f"{int(num)} {dist}", r.get("args"))
    pending = sorted(set(mentioned) - visited, key=lambda a: (a.split()[1], int(a.split()[0])))
    print(f"[duo] coverage of {run.name}: {len(visited)} visited, "
          f"{len(mentioned)} cited in clues, {len(pending)} cited-but-unvisited.")
    print(f"  visited: {', '.join(sorted(visited)) or '(none)'}")
    if pending:
        print("  CITED IN CLUES BUT NEVER VISITED (review before closing):")
        for a in pending:
            print(f"    - {a}  (appeared in clue {mentioned[a]})")
    else:
        print("  No cited addresses left unvisited.")
    print("\n[duo] Address-only backstop. Unnamed/unplaced entities are caught by the "
          "Explorer's UNRESOLVED-REPORT (authoritative).")


def main():
    argv = sys.argv[1:]
    prompt_spec = None
    if "--prompt" in argv:
        i = argv.index("--prompt")
        prompt_spec = Path(argv[i + 1]).resolve()
        del argv[i:i + 2]
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, run = argv[0], Path(argv[1]).resolve()
    if not run.exists():
        sys.exit(f"[duo] No such run: {run}")
    if cmd == "phase0":
        phase0(run)
    elif cmd == "served":
        served(run)
    elif cmd == "theorist-input":
        theorist_input(run, prompt_spec or DEFAULT_PROMPT)
    elif cmd == "verify":
        verify(run)
    elif cmd == "coverage":
        coverage(run)
    else:
        sys.exit(f"[duo] Unknown command: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
