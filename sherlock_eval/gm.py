#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic Game Master for the agent-eval harness.

Serves clues VERBATIM on demand, keeps the game state (clues followed, letters
circled, decisions), applies conditional gates, and logs EVERYTHING to
runs/<run>/log.jsonl. It is not an LLM and it never holds the solution in
memory: it loads ``case.json`` (the world) only. The answer key lives in a
separate file read by a separate component (``score.py`` / a judge), so the GM
cannot serve the solution even by accident.

Usage:
    python -m sherlock_eval init --case cases/toy-example --run runs/r1 [--mode faithful|guided]
    python -m sherlock_eval --run runs/r1 <command> [args]

Game commands (the workspace ships a ``./gm`` wrapper for these):
    visit "1 N"               visit an address (counts as a clue followed)
    reread "1 N"              re-read what was already served at an address (free)
    decide "3 C" <id> yes|no  resolve a branch a clue offered
    index "<term>"            query the unlocked index counter
    index --list              list the index terms (once unlocked)
    questions                 show the questions (guided: always; faithful: after finalize)
    status                    clues followed, letters circled, decisions
    finalize                  close the investigation (no more visits)
    submit <file>             hand in the final answers (locks the game)
"""
import datetime
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

MISS = ("[GM] There is no paragraph for that address in this case's casebook. "
        "Pick another lead (this query does NOT count as a clue followed).")

RULES = Path(__file__).resolve().parent / "rules.md"


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def norm_txt(s: str) -> str:
    """Uppercase, collapse whitespace, and strip accents (so search is
    accent-insensitive — a robust, boring detail that matters in practice)."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().upper()


def addr_normalizer(districts):
    """Build an address normalizer for this case's district codes.

    Addresses are ``<number> <district>`` (e.g. ``1 N``). The set of valid
    district codes is declared per-case in ``meta.districts`` — nothing here is
    hardcoded to any particular world."""
    codes = sorted((d.upper() for d in districts), key=len, reverse=True)
    pat = re.compile(r"(\d+)\s*(" + "|".join(re.escape(c) for c in codes) + r")$")

    def norm(s: str):
        m = pat.fullmatch(norm_txt(s.replace("-", " ")))
        return f"{int(m.group(1))} {m.group(2)}" if m else None

    return norm


def meets(req, letters, decisions) -> bool:
    """Evaluate a gate expression.

    ``req`` is ``always`` (or empty) → always shown. Otherwise it is a
    disjunction of ``|`` alternatives, each a conjunction of ``&`` tokens:
      - ``A``            letter A has been circled
      - ``!A``           letter A has NOT been circled
      - ``decision:id``  the decision ``id`` was resolved ``yes``
    """
    if not req or req == "always":
        return True
    for alt in req.split("|"):
        ok = True
        for tok in (t.strip() for t in alt.split("&")):
            if tok.startswith("decision:"):
                v = decisions.get(tok[len("decision:"):]) == "yes"
            elif tok.startswith("!"):
                v = tok[1:] not in letters
            else:
                v = tok in letters
            if not v:
                ok = False
                break
        if ok:
            return True
    return False


class GM:
    def __init__(self, run: Path):
        self.run = run
        self.case = json.loads((run / "case.json").read_text(encoding="utf-8"))
        self.state_path = run / "state.json"
        self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.norm_addr = addr_normalizer(self.case["meta"]["districts"])
        self.index_unlock = self.case["meta"]["config"].get("index_unlock_address")

    # ------------------------------------------------------------- infra
    def save(self):
        self.state_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")

    def log(self, event: str, args, text: str, **extra):
        rec = {"ts": now(), "event": event, "args": args,
               "clues_followed": self.state["counter"],
               "letters": sorted(self.state["letters"]),
               "text": text}
        rec.update(extra)
        with (self.run / "log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def emit(self, event, args, text, **extra):
        print(text)
        self.log(event, args, text, **extra)

    def check_open(self):
        if self.state.get("submitted"):
            print("[GM] The game has been submitted; only final validation remains.")
            sys.exit(1)

    # ----------------------------------------------------------- helpers
    def apply_effects(self, effects: dict):
        for letter in effects.get("circle", []):
            if letter not in self.state["letters"]:
                self.state["letters"].append(letter)
        if effects.get("unlock_index"):
            self.state["index_unlocked"] = True

    def render_clue(self, addr: str, indices: list) -> str:
        clue = self.case["clues"][addr]
        out = []
        for i in indices:
            seg = clue["segments"][i]
            out.append(seg["text"].strip("\n"))
            for doc_id in seg.get("attachments", []):
                doc = self.case["documents"][doc_id]
                out.append(f"\n[GM] — Document obtained: «{doc['title']}» —\n{doc['text']}")
        return "\n\n".join(out)

    def decision_notices(self, addr: str) -> str:
        clue = self.case["clues"][addr]
        notices = []
        for d in clue.get("decisions", []):
            if self.state["decisions"].get(d["id"]) != "yes":
                notices.append(
                    f"[GM] Decision available at {addr}: «{d['id']}» — {d['description']}.\n"
                    f"[GM] Use: ./gm decide \"{addr}\" {d['id']} yes  |  ./gm decide \"{addr}\" {d['id']} no")
        return "\n".join(notices)

    # ----------------------------------------------------------- commands
    def visit(self, arg: str):
        self.check_open()
        if self.state.get("finalized"):
            print("[GM] The investigation is finalized: no more clues can be followed.")
            return
        addr = self.norm_addr(arg)
        if not addr:
            districts = ", ".join(self.case["meta"]["districts"])
            print(f"[GM] Invalid address: {arg!r}. Format: «<number> <district>» "
                  f"(districts: {districts}), e.g. \"1 N\".")
            return
        if addr not in self.case["clues"]:
            self.emit("miss", addr, MISS, counted=False)
            return

        clue = self.case["clues"][addr]
        letters, dec = self.state["letters"], self.state["decisions"]
        served_prev = set(self.state["served"].get(addr, []))
        passing = [i for i, s in enumerate(clue["segments"]) if meets(s["requires"], letters, dec)]
        fresh = [i for i in passing if i not in served_prev]
        first = addr not in {v["addr"] for v in self.state["visits"]}

        if first:
            has_gates = any(s["requires"] != "always" for s in clue["segments"])
            has_content = (not has_gates) or any(
                clue["segments"][i]["requires"] != "always" for i in passing)
            counted = bool(self.case["meta"]["config"]["count_empty_visits"] or has_content)
        else:
            counted = bool(fresh)  # revisit: counts only if it reveals something new

        for i in passing:
            self.apply_effects(clue["segments"][i].get("effects", {}))
        if counted:
            self.state["counter"] += 1
        self.state["visits"].append({"addr": addr, "ts": now(), "counted": counted})
        self.state["served"][addr] = sorted(served_prev | set(passing))
        self.save()

        header = (f"[GM] ═══ Clue {addr} ═══ "
                  + (f"(clue followed #{self.state['counter']})" if counted
                     else "(revisit with no new information: does NOT count — use reread)"))
        body = self.render_clue(addr, passing if (first or fresh) else sorted(served_prev))
        parts = [header, body]
        notice = self.decision_notices(addr)
        if notice:
            parts.append(notice)
        if self.state["index_unlocked"] and self.index_unlock and addr == self.index_unlock:
            parts.append("[GM] Index counter available: ./gm index \"<term>\"  |  ./gm index --list")
        self.emit("visit", addr, "\n\n".join(p for p in parts if p),
                  counted=counted, segments=passing, fresh=fresh)

    def reread(self, arg: str):
        self.check_open()
        addr = self.norm_addr(arg)
        served = self.state["served"].get(addr or "", [])
        if not served:
            print(f"[GM] You have not visited {arg!r} yet; reread is only for clues already followed.")
            return
        text = (f"[GM] ═══ Rereading {addr} (free) ═══\n\n"
                + self.render_clue(addr, served))
        self.emit("reread", addr, text)

    def decide(self, arg: str, dec_id: str, value: str):
        self.check_open()
        addr = self.norm_addr(arg)
        if not addr or addr not in self.case["clues"]:
            print(f"[GM] Invalid address or no clue there: {arg!r}")
            return
        clue = self.case["clues"][addr]
        d = next((x for x in clue.get("decisions", []) if x["id"] == dec_id), None)
        if d is None:
            print(f"[GM] No decision «{dec_id}» at {addr}.")
            return
        if addr not in self.state["served"]:
            print(f"[GM] You must visit {addr} first.")
            return
        if value not in ("yes", "no"):
            print("[GM] The value must be «yes» or «no».")
            return
        if self.state["decisions"].get(dec_id) == "yes":
            print(f"[GM] Decision «{dec_id}» was already taken (yes); it cannot be undone.")
            return
        self.state["decisions"][dec_id] = value
        text = f"[GM] Decision recorded: {dec_id} = {value}."
        if value == "yes":
            self.apply_effects(d.get("effects", {}))
            letters, dec = self.state["letters"], self.state["decisions"]
            served_prev = set(self.state["served"].get(addr, []))
            passing = [i for i, s in enumerate(clue["segments"]) if meets(s["requires"], letters, dec)]
            fresh = [i for i in passing if i not in served_prev]
            for i in fresh:
                self.apply_effects(clue["segments"][i].get("effects", {}))
            if fresh:
                text += "\n\n" + self.render_clue(addr, fresh)
            self.state["served"][addr] = sorted(served_prev | set(passing))
        self.save()
        self.emit("decide", {"addr": addr, "id": dec_id, "value": value}, text)

    def index(self, term: str):
        self.check_open()
        if not self.state["index_unlocked"]:
            print("[GM] The index counter is not available (yet).")
            return
        entries = self.case.get("index", {})
        if term == "--list":
            text = "[GM] Index terms available:\n" + "\n".join(f"  - {k}" for k in entries)
            self.emit("index_list", term, text)
            return
        nt = norm_txt(term)
        matches = [k for k in entries
                   if norm_txt(k) == nt or norm_txt(k).startswith(nt) or nt.startswith(norm_txt(k))]
        if len(matches) == 1:
            k = matches[0]
            text = f"[GM] ═══ Index — «{k}» ═══\n\n{entries[k]}"
        elif len(matches) > 1:
            text = "[GM] Ambiguous term; matches: " + ", ".join(matches)
        else:
            text = f"[GM] {self.case.get('index_default', 'No entry for that term.')}"
        self.emit("index", term, text)

    def questions(self):
        if self.state["mode"] == "faithful" and not self.state.get("finalized"):
            print("[GM] Faithful mode: the questions are revealed when you finalize the investigation.")
            return
        self.emit("questions", None, self.case["questions"])

    def status(self):
        s = self.state
        followed = [v["addr"] for v in s["visits"] if v["counted"]]
        text = (f"[GM] Game status (mode {s['mode']})\n"
                f"  Clues followed: {s['counter']}  →  {', '.join(followed) or '(none)'}\n"
                f"  Letters circled: {', '.join(sorted(s['letters'])) or '(none)'}\n"
                f"  Decisions: {s['decisions'] or '(none)'}\n"
                f"  Finalized: {s.get('finalized', False)}  Submitted: {s.get('submitted', False)}")
        self.emit("status", None, text)

    def finalize(self):
        self.check_open()
        if self.state.get("finalized"):
            print("[GM] Already finalized.")
            return
        self.state["finalized"] = True
        self.save()
        ws = self.run / "workspace"
        (ws / "questions.md").write_text(self.case["questions"] + "\n", encoding="utf-8")
        text = ("[GM] Investigation finalized: no more clues can be followed "
                f"(total followed: {self.state['counter']}).\n"
                "[GM] Questions written to questions.md. Write your numbered answers in "
                "answers.md and submit with: ./gm submit answers.md\n\n"
                + self.case["questions"])
        self.emit("finalize", None, text)

    def submit(self, filename: str):
        self.check_open()
        if not self.state.get("finalized"):
            print("[GM] You must finalize the investigation first (./gm finalize).")
            return
        src = (self.run / "workspace" / filename)
        if not src.exists():
            print(f"[GM] No such file: {src}")
            return
        content = src.read_text(encoding="utf-8")
        (self.run / "answers.md").write_text(content, encoding="utf-8")
        self.state["submitted"] = True
        self.save()
        text = ("[GM] Answers submitted and the game is locked. "
                "Validation against the official solution is done by a separate component.")
        self.emit("submit", filename, text, answers=content)


def cmd_init(argv):
    args = dict(zip(argv[::2], argv[1::2]))
    case_dir = Path(args["--case"]).resolve()
    run = Path(args["--run"]).resolve()
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    mode = args.get("--mode", case["meta"]["config"].get("default_questions_mode", "faithful"))
    assert mode in ("guided", "faithful"), "mode must be guided|faithful"
    if run.exists():
        sys.exit(f"[GM] Run {run} already exists.")
    run.mkdir(parents=True)
    shutil.copytree(case_dir / "workspace", run / "workspace")
    shutil.copy2(case_dir / "case.json", run / "case.json")
    # The harness ships its OWN generic rules — the case never carries them.
    shutil.copy2(RULES, run / "workspace" / "rules.md")
    # The intro is single-sourced in case.json and written into the workspace.
    (run / "workspace" / "intro.md").write_text(
        f"# {case['meta']['title']}\n\n{case['intro']}\n", encoding="utf-8")
    state = {"mode": mode, "counter": 0, "visits": [], "served": {},
             "letters": [], "decisions": {}, "index_unlocked": False,
             "finalized": False, "submitted": False}
    (run / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    gm_path = Path(__file__).resolve()
    wrapper = run / "workspace" / "gm"
    wrapper.write_text(
        f'#!/bin/sh\nexec python3 -m sherlock_eval --run "{run}" "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    if mode == "guided":
        (run / "workspace" / "questions.md").write_text(case["questions"] + "\n", encoding="utf-8")
    gm = GM(run)
    gm.log("init", {"case": str(case_dir), "mode": mode}, f"run created at {run}")
    print(f"[GM] Run created: {run}\n[GM] Player workspace: {run / 'workspace'}\n"
          f"[GM] Questions mode: {mode}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.exit(__doc__)
    if argv[0] == "init":
        cmd_init(argv[1:])
        return
    assert argv[0] == "--run", "usage: --run <dir> <command> [args]"
    gm = GM(Path(argv[1]).resolve())
    cmd, rest = argv[2], argv[3:]
    dispatch = {
        "visit": lambda: gm.visit(rest[0]),
        "reread": lambda: gm.reread(rest[0]),
        "decide": lambda: gm.decide(rest[0], rest[1], rest[2]),
        "index": lambda: gm.index(rest[0]),
        "questions": gm.questions,
        "status": gm.status,
        "finalize": gm.finalize,
        "submit": lambda: gm.submit(rest[0]),
    }
    if cmd not in dispatch:
        sys.exit(f"[GM] Unknown command: {cmd}\n{__doc__}")
    dispatch[cmd]()


if __name__ == "__main__":
    main()
