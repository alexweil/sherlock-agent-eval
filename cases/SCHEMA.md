# Case format — bring your own case

This repo ships **none** of any commercial game's content. To reproduce the
article's method against a real case, you **transcribe a case from your own copy
of the game** into the files described here. Everything you transcribe is for
**local use only** — keep it gitignored and do not redistribute it (see
[`../NOTICE.md`](../NOTICE.md)).

The toy case in [`toy-example/`](toy-example/) is an **original** mini-mystery
written for this repo (no copyright). Read it alongside this schema — it is a
complete, runnable example of every field below.

A case is a directory with two machine files and a `workspace/` of free reading:

```
your-case/
├── case.json          # the playable WORLD — loaded by the Game Master
├── solution.json      # the answer key + rubric — loaded ONLY by the judge
└── workspace/         # free material the player may read (local-only for a real game)
    ├── map.md
    ├── directory-people.md
    ├── directory-places.md
    ├── informants.md
    └── newspaper.md
```

> **World ≠ judge (the anti-leak split).** The Game Master loads `case.json`
> only; it never has the solution in memory, so it cannot serve it even by
> accident. `solution.json` is read by a separate component. Keep them separate.

`intro.md`, `rules.md`, and `questions.md` are **generated** into the run, not
authored as files: the intro comes from `case.json`, the **rules ship with the
harness** (generic — never copy a commercial rulebook), and the questions are
written out from `case.json` (at finalize in faithful mode, at init in guided).

---

## `case.json` — the world

```jsonc
{
  "meta": {
    "id": "your-case",
    "title": "Your Case Title",
    "districts": ["N", "S", "E", "W", "C"],   // valid district codes for addresses
    "holmes": { "clues": 4, "free": [] },     // Holmes's clue count (the scoring target);
                                              // "free" = addresses that don't count, if any
    "scoring": {                              // OPTIONAL — a reference ("par") and bands.
      "reference_label": "Holmes",            //   omit the whole block and the scorer prints
      "reference_score": 70,                  //   only the raw final score (no absolute scale).
      "bands": [                              //   [max, label] pairs; null max = open-ended top.
        [30, "even good investigators come up short."],
        [55, "you solved most of the case."],
        [69, "only Holmes would have found the gaps."],
        [null, "you matched or beat the master."]
      ]
    },
    "config": {
      "count_empty_visits": true,             // a blind first visit to a gated address counts
      "default_questions_mode": "faithful",   // "faithful" (hard) | "guided"
      "index_unlock_address": "2 N"           // optional: where the index counter unlocks
    }
  },

  "intro": "Free narrative shown to the player (the assignment). Markdown ok.",

  "questions": "## Questions\n\n1. ...\n2. ...",   // BARE PROMPTS ONLY — no answers, no rubric

  "clues": {
    "<address>": {
      "segments": [
        {
          "text": "The clue text, served VERBATIM.",
          "requires": "always",               // gate expression (see below)
          "effects": { "circle": ["A"], "unlock_index": true },   // optional
          "attachments": ["doc-id"]           // optional: documents revealed with this segment
        }
      ],
      "decisions": [
        { "id": "press", "description": "what choosing 'yes' does", "effects": {} }
      ]
    }
  },

  "documents": {
    "doc-id": { "title": "Shown title", "text": "Document body, served verbatim." }
  },

  "index": {                                  // optional: the unlockable counter index
    "TERM": "what the clerk tells you for TERM"
  },
  "index_default": "Reply when a term is not in the index."
}
```

### Addresses

Every location is `<number> <district>` (e.g. `2 N`). The district codes are
whatever you declare in `meta.districts` — nothing is hardcoded to any world.
Address matching is case-, space-, and accent-insensitive.

### Gate expressions (`requires`)

A segment is shown only when its gate passes:

- `always` (or empty) — always shown.
- `A` — letter `A` has been circled by some earlier clue/decision.
- `!A` — letter `A` has **not** been circled.
- `decision:press` — the decision `press` was resolved `yes`.
- Combine with `&` (and) and `|` (or): `A & !B`, `A | decision:press`.

This is how visit **order** changes what you can see: a clue at one address
circles a letter that unlocks a paragraph at another. (In the toy case, `5 C`
circles `A`, which unlocks the gated paragraph at `8 W`.)

### Effects

- `"circle": ["A", "B"]` — circle these letters (they gate other segments).
- `"unlock_index": true` — unlock the `index` counter (queried with `./gm index`).

Effects on a segment fire when that segment is served; effects on a `decision`
fire when it is resolved `yes`.

### Counting

- A **first** visit to a real address counts, even if a gate hides its content
  (set `count_empty_visits` to control this).
- A **revisit** counts only if it reveals new content; otherwise it is a free
  `reread`.
- A **miss** (an address not in `clues`) never counts.

---

## `solution.json` — the answer key (judge only)

```jsonc
{
  "questions": [
    {
      "n": 1,
      "points": 20,
      "answer": "The canonical answer.",
      "rubric": "Full (20): ... Half (10): ... Zero: ..."
    }
  ]
}
```

This file is read **only by the judge** — it is the one component that ever sees
the solution. Holmes's clue count is **not** here: it lives in `case.json`
(`meta.holmes.clues`, part of the world), so the scorer never needs the solution.

The judge (`prompts/judge.md`) reads this, grades the player's `answers.md`, and
writes `grades.json` (`{"1": 20, "2": 30, ...}`). The scorer
(`python -m sherlock_eval score`) then combines `grades.json` with the GM's clue
count and `meta.holmes.clues` from `case.json` — it never reads `solution.json`.

---

## `workspace/` — the free material

These are the files the player reads for free. For a **real** game you transcribe
them from your own copy; they are local-only and gitignored. The required set:

| File | What it is |
|---|---|
| `map.md` | districts and the address system |
| `directory-people.md` | person/entity → address (the player greps it) |
| `directory-places.md` | place/service → address |
| `informants.md` | recurring informants and their addresses |
| `newspaper.md` | the day's paper — ads/articles dense with case material |

`rules.md` and `intro.md` are added automatically at `init` (do not put them
here). You may add other free files if your case has them.

---

## Authoring checklist

1. Pick district codes and write `map.md`.
2. Transcribe the directories and `newspaper.md` (verbatim from your copy, local
   only).
3. Write `case.json`: intro, questions (bare), clues (with gates/effects/
   attachments), documents, optional index, and `meta.holmes.clues`.
4. Write `solution.json`: per-question answer, points, and rubric.
5. Smoke-test: `python -m sherlock_eval init --case cases/your-case --run runs/t`
   then play a few `visit`s, `finalize`, write `answers.md`, `submit`, and
   `score` with a hand-written `grades.json`.
6. **Leakage audit** before sharing anything: see [`../README.md`](../README.md).
   Never commit a real game's transcribed content.
