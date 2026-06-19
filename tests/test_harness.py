"""Scripted-solver tests over the toy case — no model required.

These drive the deterministic Game Master through the real CLI dispatch (so the
state.json disk round-trip is exercised on every command) and assert the GM
mechanics and the scorer. They also assert the harness's anti-leak guarantee:
the run directory the GM reads never contains the solution.
"""
import json

import pytest

from conftest import TOY_CASE
from sherlock_eval import gm, score


@pytest.fixture
def run(tmp_path):
    """An initialized faithful-mode run of the toy case."""
    run_dir = tmp_path / "run"
    gm.main(["init", "--case", str(TOY_CASE), "--run", str(run_dir), "--mode", "faithful"])
    return run_dir


def play(run, *args):
    gm.main(["--run", str(run), *args])


def state_of(run):
    return json.loads((run / "state.json").read_text())


# ---------------------------------------------------------------- structure

def test_init_does_not_leak_the_solution(run):
    """The GM loads case.json only; the answer key is never in its reach."""
    assert (run / "case.json").exists()
    assert not (run / "solution.json").exists()
    case = json.loads((run / "case.json").read_text())
    blob = json.dumps(case)
    # The world file carries no rubric / answer-key fields.
    assert "rubric" not in blob and "points" not in blob


def test_workspace_is_self_contained(run):
    ws = run / "workspace"
    for f in ["rules.md", "intro.md", "map.md", "newspaper.md",
              "directory-people.md", "directory-places.md", "informants.md", "gm"]:
        assert (ws / f).exists(), f
    # generic rules came from the harness, not the case
    assert "harness rules" in (ws / "rules.md").read_text()


# ---------------------------------------------------------------- mechanics

def test_miss_does_not_count(run, capsys):
    play(run, "visit", "9 N")
    out = capsys.readouterr().out
    assert "no paragraph for that address" in out
    assert state_of(run)["counter"] == 0


def test_letter_gate_hides_then_reveals(run, capsys):
    # 8 W before letter A: the gated paragraph (the wire) is hidden.
    play(run, "visit", "8 W")
    out = capsys.readouterr().out
    assert "Private wires are private" in out
    assert "T. Thorn" not in out

    # 5 C circles letter A.
    play(run, "visit", "5 C")
    capsys.readouterr()
    assert "A" in state_of(run)["letters"]

    # revisiting 8 W now reveals the wire and counts (new content).
    play(run, "visit", "8 W")
    out = capsys.readouterr().out
    assert "T. Thorn" in out and "WORTHLESS WITHOUT HER" in out
    counted = [v for v in state_of(run)["visits"] if v["addr"] == "8 W" and v["counted"]]
    assert len(counted) == 2  # blind visit + the revealing revisit both count


def test_index_locked_until_unlock_visit(run, capsys):
    play(run, "index", "Hale")
    assert "not available" in capsys.readouterr().out

    play(run, "visit", "2 N")           # unlocks the index
    capsys.readouterr()
    assert state_of(run)["index_unlocked"] is True

    play(run, "index", "Hale")
    assert "SS Marlow" in capsys.readouterr().out

    play(run, "index", "Nobody")        # default response for unknown terms
    assert "no such name" in capsys.readouterr().out.lower()


def test_decision_gates_payoff_across_addresses(run, capsys):
    # 3 S before the decision: only the decoy paragraph (Crale), not the payoff.
    play(run, "visit", "3 S")
    out = capsys.readouterr().out
    assert "here is your killer" in out
    assert "Eleanor Hale" not in out

    # the decision lives at 7 E.
    play(run, "visit", "7 E")
    capsys.readouterr()
    play(run, "decide", "7 E", "press", "yes")
    out = capsys.readouterr().out
    assert "her sister" in out

    # revisiting 3 S now reveals the 'alive' payoff.
    play(run, "visit", "3 S")
    out = capsys.readouterr().out
    assert "very much alive" in out and "Eleanor Hale" in out


def test_faithful_mode_withholds_questions(run, capsys):
    play(run, "questions")
    assert "revealed when you finalize" in capsys.readouterr().out

    play(run, "finalize")
    out = capsys.readouterr().out
    assert "Who killed Silas Dunmore" in out


def test_submit_locks_the_game(run, capsys):
    play(run, "finalize")
    capsys.readouterr()
    (run / "workspace" / "answers.md").write_text("1. ...\n2. ...\n3. ...\n")
    play(run, "submit", "answers.md")
    assert "locked" in capsys.readouterr().out
    assert state_of(run)["submitted"] is True
    with pytest.raises(SystemExit):
        play(run, "visit", "1 N")


# ---------------------------------------------------------------- scoring

def test_optimal_path_ties_holmes(tmp_path, capsys):
    """The 4-clue solution (no decoy, gate ordered right) equals Holmes's count,
    so a perfect answer scores 70 with a zero clue adjustment."""
    run = tmp_path / "run"
    gm.main(["init", "--case", str(TOY_CASE), "--run", str(run), "--mode", "faithful"])
    for cmd in (["visit", "5 C"], ["visit", "8 W"], ["visit", "2 N"], ["visit", "7 E"]):
        play(run, *cmd)
    capsys.readouterr()
    assert state_of(run)["counter"] == 4

    (run / "grades.json").write_text(json.dumps({"1": 20, "2": 30, "3": 20}))
    text = score.run_score(run)
    assert "Adjustment: 5 × (4 − 4) = +0 pts" in text
    # reference + band come from case.json meta.scoring, not a hardcoded 100-scale.
    assert "Final score: **70 pts** (Holmes: 70)" in text
    assert "you matched or beat the master" in text


def test_scoring_block_is_optional(run):
    """With no meta.scoring, the scorer prints only the raw final score — no
    reference and no band (it never invents an absolute scale)."""
    case = json.loads((run / "case.json").read_text())
    case["meta"].pop("scoring", None)
    (run / "case.json").write_text(json.dumps(case))
    (run / "grades.json").write_text(json.dumps({"1": 20, "2": 30, "3": 20}))
    text = score.run_score(run)
    assert "Final score: **90 pts**" in text   # 70 + 5*(4-0)
    assert "Band:" not in text
    assert "(Holmes" not in text               # no reference parenthetical


def test_extra_clue_costs_five(tmp_path):
    run = tmp_path / "run"
    gm.main(["init", "--case", str(TOY_CASE), "--run", str(run), "--mode", "faithful"])
    for addr in ("5 C", "8 W", "2 N", "7 E", "3 S"):   # one extra (the decoy) → 5 clues
        play(run, "visit", addr)
    assert state_of(run)["counter"] == 5
    (run / "grades.json").write_text(json.dumps({"1": 20, "2": 30, "3": 20}))
    text = score.run_score(run)
    assert "= -5 pts" in text
    assert "Final score: **65 pts**" in text


def test_solution_rubric_points_sum_to_seventy():
    sol = json.loads((TOY_CASE / "solution.json").read_text())
    assert sum(q["points"] for q in sol["questions"]) == 70
