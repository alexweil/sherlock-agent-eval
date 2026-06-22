# sherlock-agent-eval

**A Sherlock Holmes board game as an LLM-agent eval**

You give an agent a case; it decides which people and places to investigate; each
lead it follows hands it a passage of text served **verbatim** by a deterministic
Game Master; at the end it answers the case's questions and is scored against
"Holmes" — including how *few* leads it needed. A printed detective game makes a
surprisingly honest agent eval: the solution is physically hidden, information has
a price, and it rewards comprehension over retrieval.

📄 **Read the write-up:** [the article](docs/index.md) — *"How good a detective is an AI?"*
(Also served via GitHub Pages from `docs/`.)

---

## ⚠️ Copyright / content notice (read this first)

**This repo ships no game content.** It is the evaluation *machinery* — Game
Master, scorer, agent prompts, the case **format**, and an **original** synthetic
toy case written for this repo. It contains **no** text, clues, solutions, or
transcripts from any commercial game.

To reproduce the article against a **real** case you must **own the game** and
**transcribe a case from your own copy** into the case files
([`cases/SCHEMA.md`](cases/SCHEMA.md)). Anything you transcribe is **local-only**:
keep it gitignored and **do not redistribute it**. See [`NOTICE.md`](NOTICE.md).
Not affiliated with Space Cowboys or any rights holder.

## What this is, honestly (V1)

This is **V1: harness + article + schema + toy case + tests + a documented
protocol.** It reproduces the *evaluation machinery* and ships a runnable
synthetic case. It does **not** include the original commercial case and does
**not** reproduce the article's results table — those came from a transcribed
case we cannot redistribute. The full provider-agnostic API driver (run the
monolith and duo automatically against a model) is deferred to **V2**;
contributions welcome.

## Requirements (tiered)

| You want to… | You need |
|---|---|
| Run the **toy case** and the tests | **Python ≥ 3.9 only** (no model, no API key) |
| Reproduce with **your own** commercial case | your own copy of the game (to transcribe) |
| Run the agents (monolith / duo) for real | **model access** (you wire it; V2 will automate) |

## Quick start (toy case, Python only)

```bash
pip install -e ".[dev]"     # or: make install
make test                   # scripted-solver tests over the toy case — no model

# play the toy case by hand:
python -m sherlock_eval init --case cases/toy-example --run runs/demo --mode faithful
cd runs/demo/workspace
./gm visit "5 C"            # the dead man's room (a decoy + circles letter A)
./gm visit "8 W"            # the telegraph office (gated by letter A → the killer)
./gm visit "2 N"            # the quay (the decisive behavioral clue + unlocks the index)
./gm index "Hale"           # the unlocked counter index
./gm visit "7 E"            # the lamplighter (offers a decision)
./gm decide "7 E" press yes
./gm finalize               # reveals the questions (faithful mode)
# write numbered answers into answers.md, then:
./gm submit answers.md
```

Then grade and score (see *Scoring* below).

## The world & the commands

The agent works entirely inside `runs/<run>/workspace/`. The world is a grid of
addresses; everything else is free to read.

- **Addresses.** Every location is `<number> <district>` (e.g. `5 C`, `38 CE`).
  You reach one by resolving a name into an address through two **directories** —
  person→address and place→address — that the agent searches with `grep` (in a
  full case they run to a couple thousand entries, too large to read whole).
- **Free material** (zero cost, unlimited): the case intro, the rules, a map, a
  list of recurring informants, and the day's **newspaper**. Thinking, rereading,
  directory lookups, and `status` are all free — only **visiting** an address
  buys a new clue.

**Command surface** — the agent drives the Game Master with `./gm <cmd>`:

| Command | Cost | What it does |
|---|---|---|
| `visit "<addr>"` | **1 clue** | returns that address's clue **verbatim** — the only paid action |
| `reread "<addr>"` | free | re-read a clue you already paid for |
| `decide "<addr>" <branch> <choice>` | free | resolve a branch a clue offers |
| `index "<name>"` | free | a counter/index lookup, unlocked by a specific visit |
| `status` | free | progress so far: clues followed, letters circled, decisions |
| `questions` | free | show the case's questions (in **faithful** mode, only after `finalize`) |
| `finalize` | — | end the investigation and reveal the questions |
| `submit answers.md` | — | hand in answers — **irreversible** |

**Scoring rules that shape strategy** (the formula is in [Scoring](#scoring)):

- Some clues **circle a letter** that gates conditional paragraphs at *other*
  addresses, so visit order changes what you can see.
- A first visit to a real address counts even if a letter-gate hides its content
  (visiting blind is punished); a re-visit counts only if it reveals new content;
  a **"miss"** (an address with no clue this case) doesn't score, but the audit
  flags it as wasted motion.
- **Faithful mode** (`--mode faithful`, used in the Quick start) withholds the
  questions until you `finalize` — you investigate without knowing what you'll be
  asked.

## Repo layout

```
sherlock-agent-eval/
├── sherlock_eval/        # the engine (the package; python -m sherlock_eval)
│   ├── gm.py             #   Game Master — loads case.json (the WORLD), never the solution
│   ├── score.py          #   final scorer — combines judge grades + the clue count
│   └── rules.md          #   the harness's OWN generic rules (never a commercial rulebook)
├── drivers/
│   ├── dupla.py          #   duo (Theorist + Explorer) orchestration helper
│   └── monolith.py       #   single-agent helper (clean-context served-clues)
├── prompts/              # English, generic — audited for case strings
│   ├── theorist.md  explorer.md  player.md  judge.md
├── cases/
│   ├── SCHEMA.md         # ⭐ how to transcribe YOUR case (no real data)
│   ├── toy-example/      # our original synthetic case (runs out of the box)
│   └── your-case/        # gitignored — put your transcribed case here
├── tests/                # scripted solver over the toy case (no model needed)
├── docs/                 # the article + diagram (GitHub Pages)
├── pyproject.toml  Makefile  LICENSE  LICENSE-docs  NOTICE.md  .gitignore
```

## How it works (the anti-cheat thesis, enforced structurally)

- **World ≠ judge.** The Game Master loads `case.json` (the world) **only** — it
  never has the solution in memory, so it **cannot serve it even by accident**.
  The answer key (`solution.json`) is read **only by the judge**
  (`prompts/judge.md`); the scorer (`score.py`) reads only the judge's grades plus
  the clue counts — it never touches the solution either.
- **Deterministic GM.** Plain Python, not an LLM. It serves clues verbatim,
  applies letter-gates and decisions, counts clues, and logs every event to
  `runs/<run>/log.jsonl`.
- **Information has a price.** Thinking, rereading, directory lookups, and the
  newspaper are free and unlimited; only **visiting** an address yields a new
  clue, and clues over Holmes's count cost points.
- **Audit, not a sandbox.** Isolation is convention + audit: the agent sees only
  its workspace; the judge cross-checks the served log against the answers. A run
  with knowledge that has no served origin is discarded.

## Bring your own case

The repo replaces game content with a **format contract**. See
[`cases/SCHEMA.md`](cases/SCHEMA.md): you author `case.json` (the world),
`solution.json` (the answer key + rubric), and a `workspace/` of free material
(map, directories, informants, newspaper) transcribed from **your own copy**. The
[`toy-example/`](cases/toy-example/) is a complete worked example.

## Running the configurations (how they map to the article)

The harness ships **prompts + protocol**; you relay between the model and `./gm`.
(V2 will automate this against an API.)

- **Baseline / methodical monolith** — one agent with `prompts/player.md`, using
  the workspace and `./gm` directly. The methodical prompt cleans up *process*;
  in the article it still fell for the comprehension trap.
- **Clean-context monolith** — the same single agent, but re-spawned **fresh**
  each turn with only `notes.md` + `served-clues.md` as memory. Regenerate the
  latter each turn: `python drivers/monolith.py served runs/<run>`.
- **Duo (Theorist + Explorer)** — two agents with isolated contexts, the move
  that broke the comprehension trap in the article. The **Theorist**
  (`prompts/theorist.md`) reasons with no world access; the **Explorer**
  (`prompts/explorer.md`) acts and relays verbatim; a conductor is a verbatim
  pipe. Drive it with `drivers/dupla.py` (`phase0`, `served`, `theorist-input`,
  `coverage`, `verify`). The closing handshake (`CLOSE` → Explorer
  `UNRESOLVED-REPORT` → `CLOSE-FINAL`) enforces naming-completeness.

## Scoring

1. A **judge** (`prompts/judge.md`) — the only component that reads the
   solution — grades `answers.md` against `solution.json` and writes
   `grades.json` (`{"1": 20, "2": 30, ...}`).
2. The scorer combines it with the GM's clue count and Holmes's count:
   ```bash
   python -m sherlock_eval score --run runs/<run>
   ```
   **final = answer points + 5 × (Holmes's clue count − your net clues).**

For tests and quick checks you can hand-write `grades.json` (no model needed).

## Leakage audit (before you publish anything)

If you transcribe a real case, audit before sharing **any** change:

- `.gitignore` already excludes `cases/*/` (except the toy case) and `runs/`.
- Grep the harness against a **private denylist** of case strings (character
  names, real addresses, the real case title, document ids):
  ```bash
  ./scripts/leakcheck.sh /path/to/private-denylist.txt   # kept OUTSIDE the repo
  ```
  **Never commit the denylist** — committing the list of case names *is* the
  leak. Keep it outside the repo; run the check as a pre-push step. `docs/` (the
  paraphrased, attributed article) is excluded by design — audit it by eye.

## License & ethics

- **Code:** Apache-2.0 ([`LICENSE`](LICENSE)).
- **Article / diagrams / docs:** CC BY 4.0 ([`LICENSE-docs`](LICENSE-docs)).
- **Content & affiliation:** [`NOTICE.md`](NOTICE.md) — ships no game content;
  bring your own copy; not affiliated with any rights holder.
