# Rules of play (harness rules — generic)

These are the harness's own rules, written for this eval. They describe the
*mechanics* of play, not any particular published game.

## The world

- Every location is an address: `<number> <district>`, e.g. `1 N`. The valid
  district codes are listed in the case's `map.md`.
- To find where to go, resolve a **name → address** using the directories
  (`directory-people.md`, `directory-places.md`). They are large — search them
  with `grep` rather than reading them whole.

## What is free vs. what costs

- **Free and unlimited:** thinking, re-reading, and cross-referencing. The
  intro, map, directories, informants, and newspaper are all free; so are
  `reread`, `status`, and `index` lookups.
- **Paid:** the only way to get a *new* clue is to **visit** an address. Every
  clue you follow beyond what Holmes used costs points (see scoring).

## Commands

```
./gm visit "1 N"              # visit an address → returns its clue VERBATIM (paid)
./gm reread "1 N"             # re-read a clue already followed (free)
./gm decide "3 C" <id> yes|no # resolve a branch a clue offered
./gm index "<term>"          # query the index counter (once a visit unlocks it)
./gm index --list            # list the index terms
./gm status                  # clues followed, letters circled, decisions
./gm questions               # show the questions (guided: anytime; faithful: after finalize)
./gm finalize                # close the investigation → reveals the questions
./gm submit answers.md       # hand in your answers (FINAL, irreversible)
```

## Gates, letters, and decisions

- Some clues **circle a letter**. A circled letter can unlock conditional
  paragraphs at *other* addresses, so visit order changes what you can see.
- Some clues offer a **decision** (`./gm decide`). Resolving it `yes` can reveal
  extra content or unlock further paragraphs.

## Counting (this shapes your strategy)

- A **first** visit to a real address counts even if a letter-gate hides its
  content (visiting blind is punished).
- A **revisit** counts only if it reveals new content; otherwise use `reread`
  (free).
- A **miss** — an address with no clue this case — does **not** count, but it is
  logged as wasted motion.

## Scoring

- Your answers earn points. Then:
  **final = answer points + 5 × (Holmes's clue count − your net clues).**
- Every clue over Holmes's count costs 5; every one under earns 5. You are not
  told Holmes's count during play.

## Modes

- **guided:** the questions are visible from the start.
- **faithful (hard mode):** the questions are withheld until you `finalize` —
  you investigate without knowing what you will be asked.

## Integrity

- Work only inside your workspace. The GM's internals and the solution live
  outside it; do not look for them. Everything is logged and audited; a run with
  knowledge that has no served origin is discarded.
