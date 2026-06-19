---
title: "A Sherlock Holmes board game as an LLM-agent eval"
description: "Topology beat model size."
---

# A Sherlock Holmes board game as an LLM-agent eval — topology beat model size

I took a Sherlock Holmes detective board game and turned it into an eval for LLM agents. If you've never played one: it's an open-ended deduction game. You're handed a case, you decide which people and places around Victorian London to go investigate, each lead you follow hands you a passage of text, and at the end you answer the case's questions — and your solution is scored against Holmes's own, including how *few* leads you needed to get there.

The agent plays the **Irregulars** — the Baker Street street kids Holmes sends out to do his legwork.

On its first run, **Claude Fable 5 tied Holmes** — in the hard mode, where you don't even get to see the questions until the investigation is over.

That's the headline. But the score isn't the story. The interesting part is the two distinct ways these agents fail — and that the harder failure has a clean fix that turned out to be less about model size than I expected.

## Why a board game is a surprisingly honest agent eval

Most agent benchmarks have a problem: the answer is somewhere in the context, or the task is gameable, or "success" is graded loosely. A printed detective game sidesteps all three by construction:

- **The solution is physically hidden.** In the box, the answers are printed at the back, upside down; the player isn't supposed to look. The solution isn't in the agent's allowed workspace; reading it would be a detectable protocol violation, and I audit for it.
- **Information has a price.** Thinking, re-reading, and cross-referencing are free and unlimited. But *acting* — visiting a location to pull a new clue — is the only way to get new information, and every new clue beyond what Holmes used **costs points**. That's a miniature of real agent economics: every tool call costs something.
- **It rewards comprehension, not retrieval.** Clues are behaviors and details you have to assemble into one coherent story; none of them hands you the answer.

The mechanics that make this auditable, in one breath: the agent works in a sandbox containing only what it's allowed to see; a **deterministic Game Master** (plain Python, not an LLM) serves clues verbatim and logs everything; visits cost points and the solution lives outside the agent's reach; and a separate validator — the only component that reads the solution — cross-checks the log against the answers afterward. (Full mechanics in *How it's built*, below.)

A note on words: I'll call it **cheat-resistant**, not cheat-proof. It's a commercial game, so I can't rule out that some of the case leaked into pretraining, or that an agent could *steer* its exploration with latent knowledge it never names in an answer. What I *can* show is that the agents' mistakes are consistent with only the information they were served — strong evidence, not proof.

## The two ways it fails

Across a ladder of models (Claude Haiku 4.5 → Claude Sonnet 4.6 → Claude Opus 4.8 → Claude Fable 5), two failure modes show up again and again. They're worth naming because they're not specific to board games — they're how LLM agents fail at any multi-step retrieval-and-reasoning task.

### Failure 1 — Execution: preferring what you generated to what you retrieved

The case's undercover agent uses a cover name. **Claude Fable 5 — the strongest player overall — actually found the real name in a served clue and wrote it into its own notes.** Then, at answer time, it crossed it out and replaced it with a *cleverer* name it had constructed itself: an anagram of a passenger-list name that looked like it "decoded" into something elegant.

It had the right answer, retrieved, on the page in front of it. It overrode it with a guess it generated, because the guess felt more clever. This happened in both of Claude Fable 5's clean single-pass runs. The checkpointed run is revealing: a third Claude Fable 5 run had to be restarted mid-game (rate-limiting), so it resumed as a *fresh* agent reading only its externalized notes — and, taking that retrieved fact at face value instead of re-deriving it, it kept the correct name. It was the only Claude Fable 5 run to both escape the decoy trap *and* name the agent correctly — and it got there precisely by trusting a fact in its notes over a freshly-generated guess.

If you build RAG or research agents, you know this bug — the one where the model confidently hallucinates *over* a document it just retrieved. Here it is, isolated and measurable: **recency plus a bias toward self-generated content beats recalled fact.** The freshly-generated inference (recent, *mine*) wins over the served fact (old, someone else's) buried in a long append-only history.

### Failure 2 — Comprehension: the obvious suspect is a decoy

The case is built around a decoy. The murdered man is, on the surface, the obvious "agent" — a former detective, an American who just arrived in London. Every detail invites you to conclude he's the target.

He isn't. The real undercover agent is a *living* woman the killer is *still hunting*. The decisive clue isn't a fact — it's a **behavior**: after the murders, the killer is back at the shipping office that morning, scanning the passenger list. If the dead man were the agent, why is the killer still looking? You don't hunt a corpse.

Call this **the decoy trap**: the obvious suspect is a stand-in, and the real answer is the one you have to *infer* is still out there. Escaping it — reading a clue as a behavior, noticing the behavior contradicts the obvious story, concluding the obvious story is wrong — is **second-order** reasoning. And it's where almost every configuration falls down: a single-agent "methodical detective" prompt, run across nine playthroughs of this one case, fell for the decoy trap **9 times out of 9.**

These two failures organize everything else: *execution* errors (you understood it and fumbled it) versus *comprehension* errors (you never understood it).

## What actually fixes each failure (the evidence)

I tried a ladder of interventions, each isolating one lever. The honest summary: most things help the *easy* failure (execution) and the *process*; the *hard* one (comprehension) was stubborn until I changed the agent topology.

- **A generic "good investigator" prompt** (exhaust the free material first, cite your sources, build one model of the world, distrust the obvious). This cleaned up the *process* beautifully — exploration got disciplined, fabrication (the anagram) disappeared. But comprehension didn't move: the decoy trap held 9/9. **You can teach an agent to *behave* like a good investigator without teaching it to *understand* the case.**
- **Letting it know the questions up front** (instead of the hard mode). This *can* touch comprehension — but it's model-dependent. Claude Sonnet 4.6 jumped and cracked the trap; Claude Opus 4.8 didn't benefit; Claude Haiku 4.5 couldn't use it. The lesson: *the trap is built during the investigation, so a hint during the investigation helps; cleaning up only at answer time is too late.*

Neither reliably broke the comprehension trap. The thing that did was **splitting the agent in two.**

### Split comprehension from exploration

The move: instead of one agent that both explores and reasons, use **two agents that cooperate**:

- A **Theorist** — the comprehension engine. It has *no access to the world*: it can't `grep`, can't visit anything, never sees the directory or the GM's raw output. Its only job is to maintain a single model of the world, label every fact with its source, hunt loose ends, try to *falsify* its own leading hypothesis, and decide what to investigate next. It's re-spawned fresh every turn from an externalized ledger, so it never accumulates a contaminated transcript of dead-ends — which means the model of the world it "maintains" doesn't really live in the agent at all: it lives in the ledger text and is rebuilt, in-context, every turn. The case-model is a document the Theorist rewrites, not a state it holds. (That's the same property that helped the checkpointed Fable run keep the right name: when your world-model is a *file*, it's easier to trust the written fact over a fresh guess.) It doesn't see the questions until it decides to close.
- An **Explorer** — the perception/action engine. It has the workspace and the Game Master. It takes a loose-end from the Theorist, resolves the name→address, visits, and relays the clue back **verbatim**. It's explicitly forbidden from concluding anything about the case.
- A **conductor** between them is a pure verbatim pipe.

![Two agents, split by job. A Theorist that only reasons — no world access, no search, no Game Master, fresh context each turn — is walled off from an Explorer that only acts, linked by a Conductor that relays requests and clues verbatim. The Explorer greps local directories for free and visits the Game Master at the cost of one clue; the Game Master holds the hidden solution.](duo-architecture.png)

Why would this help? Not because the context is cleaner — the clean-monolith control below keeps it clean and still falls. My read is that the Theorist never *does* the exploration: it never builds the obvious-reading-first frame that hunting for clues instills, and it isn't committed to a story its own legwork kept reinforcing. Blinded from the mechanics of exploring, it reads each clue cold. And here's the part worth being precise about: this isn't the Theorist *connecting* facts the monolith couldn't. The monolith had the same served clues, the same model, and the same fresh-memory setup — stitching scattered facts into a relation is something both can do. What differs is the *prior* that stitching runs under, plus the standing order that shapes it: the Theorist's one job is to *falsify* its leading hypothesis, not defend it. The second-order move isn't "connect A and B" — it's "use B to kill the hypothesis that A made tempting." Given the same `still-hunting` clue, the monoliths that reached it still misread it — but the Theorist made the call out loud:

> *"They tortured the sister for hours to extract an identity. If the dead brother were the infiltrated agent, they'd already have him — they wouldn't need to drag a name out of her. The killer is still acting on an open order. Therefore the agent is alive, and it isn't the dead man."*

That's the second-order inference, made in plain text, by an agent that never touched a directory.

### "But is it really the architecture?" — interrogating my own conclusion

This is where the article has to practice what it preaches. *"Comprehension is a topology problem"* is a big claim, and good detective work — the entire subject of this article — means distrusting your obvious conclusion until you've ruled out the alternatives. There were two.

**Alternative 1: maybe it's just the clean context.** The Theorist gets a fresh context each turn; the failing monolith doesn't. So I built a **clean monolith**: a *single* agent — still Claude Opus 4.8 — that explores and reasons itself, but is re-spawned fresh each turn with the same externalized memory the Theorist gets. Same cleanliness, no role-split. Across 3 runs it **fell for the trap 3/3.** One run even visited the shipping office, *saw* the killer still hunting, and *still* concluded the dead man was the agent. **Clean context didn't reproduce the effect.**

**Alternative 2: maybe it's just that Claude Opus 4.8 is the smart one.** So I ran the duo with **Claude Sonnet 4.6 in both roles** — a weaker model in the reasoning seat. It **broke the trap**, with the same second-order inference, and *held* it when a later clue re-baited it (revealing the dead man's old detective past — the exact detail that re-snared all three Claude Opus 4.8 monoliths).

Here's the whole evidence matrix, which is the part of this article I'd most want a skeptic to audit:

| Configuration | What it is | Escaped the decoy trap? |
|---|---|---|
| **Baseline** | one agent per model, no scaffolding (the model ladder) | **mixed**: Claude Fable 5 escaped; Claude Haiku 4.5 / Claude Sonnet 4.6 / Claude Opus 4.8 fell |
| **Methodical-prompt monolith** | one agent with generic "good investigator" instructions | **fell 9/9** (Claude Opus 4.8 among them) |
| **Clean-context monolith** | one agent (Claude Opus 4.8) that explores *and* reasons, re-spawned fresh each turn | **fell 3/3** |
| **Reasoner + explorer duo** | Claude Opus 4.8 reasons, Claude Sonnet 4.6 explores | **broke 2/2** |
| **Same duo, weaker reasoner** | Claude Sonnet 4.6 in both roles | **broke 1/1** |

Where it applies, each of these is N=3 per model, run independently — I'm reporting the binary trap outcome, not a hand-picked best run. (The baseline ladder and the methodical prompt are 3 runs per model; the controls and the duos are the run counts shown.)

Read across it and the careful claim falls out:

> **Model capability alone was neither necessary nor sufficient.** Not *sufficient*: a strong model (Claude Opus 4.8) falls for the trap as a monolith, even with clean context. Not *necessary*: a weaker model (Claude Sonnet 4.6) breaks it in the right role-split. The lever that moved the comprehension failure wasn't the model and wasn't the clean context — it was **separating the agent that reasons from the agent that explores.** (One model, Claude Fable 5, escaped solo — so capability *can* get there. It's just not the lever that generalized.)

## How it's built (for the curious)

**The world is a grid of addresses.** Every location is `<number> <district>`, e.g. `38 CE`. To find where to go, you resolve a name into an address using two **directories** (~2,300 entries: person→address and place→address), which the agent searches with `grep` — they're too big to read whole.

**The free material** (zero cost, in the agent's workspace): the case intro, rulebook, a map, a list of recurring informants, and the **newspaper** of the day — ads and articles dense with case material. **The paid action** is one command, `./gm visit "38 CE"`, returning that address's clue *verbatim*. Around it: `reread` (re-read a paid clue, free), `decide` (resolve a branch a clue offers), `times` (a newspaper-counter index, unlocked by a specific visit), `finalize` (end and reveal the questions), and `submit` (hand in answers, irreversible).

**The scoring and the rules that shape strategy:**
- **Final score = answer points + 5 × (Holmes's clue count − yours).** Holmes solved this case in 7 clues; every clue over 7 costs 5, every one under earns 5.
- Some clues "circle a letter" that **gates** conditional paragraphs at *other* addresses, so visit order changes what you can see.
- A first visit to a real address counts even if a letter-gate hides its content (visiting blind is punished); a re-visit counts only if it reveals new content; a **"miss"** (an address with no clue this case) doesn't count toward the score, but the audit flags it as wasted motion.
- The hard mode — I'll call it **faithful** — withholds the questions until you `finalize`; you investigate without knowing what you'll be asked.

**Isolation** is convention + audit, not a hard sandbox: the agent's directory holds only permitted material; the GM's internals and the solution live outside it; the prompt forbids leaving. The validator cross-checks the served log against the answers — knowledge with no served origin gets the run discarded. In practice the errors are the support: agents' correct case-specific facts traced back to served clues, and even their *wrong* answers were explainable as transformations of served text (Claude Fable 5's anagram was built from a name on a served passenger list, not conjured from outside). The tell of leakage would be the opposite — an agent naming the actual hidden solution it was never given — and that never appeared.

**The duo, implemented:** the Theorist is spawned with no `./gm` and a clean directory containing only its assembled input (free material + verbatim served clues + its prior ledger); it writes a fresh ledger each turn. The Explorer runs in the workspace and is the only one touching `./gm`. The conductor relays between them, logging every hand-off, and before the first paid visit hands the Theorist all the free material so it can build an initial world-model for free. The directories stay out of the Theorist's head — they're a lookup service the Explorer provides on request.

## The honest part (what I ruled out, and what I couldn't)

Two alternatives these controls ruled out as sole explanations in this setup: clean context alone didn't reproduce the effect, and the big model wasn't required. What honestly survives:

- **It's one case.** The decoy trap is a single instance of second-order reasoning in a single case. Two duos breaking it three times total is a strong signal, not a law. Replicating on a second case (with its own trap) is the obvious next step — and the one thing I can't yet claim.
- **The bottleneck moves.** Solving comprehension just reveals the next wall: actually reaching the leaf-clues that supply proper names. The duo understood the whole plot and still missed the agent's literal name — it lived behind a thread it never pulled.
- **Mundane things matter as much as the clever ones.** In one duo run, the biggest single jump in score came not from the architecture but from the Explorer searching the directory *with the right accent* — an earlier run had missed an entire storyline because its `grep` was accent-sensitive and silently returned nothing. A Unicode-normalization bug cost more points than the scaffolding earned. Robust, boring search is underrated.
- **The score is noisy; the binary result isn't.** Using an LLM as the grader introduces real variance (±25 points on the *same* answers, Claude Fable 5 vs Claude Opus 4.8). Treat every number here as color. The claim I stand behind is binary and grader-independent: *did it fall for the decoy trap, or not.*

## Lessons for people building agents

1. **Retrieved beats generated — but your agent doesn't believe that.** The deepest failure here is an agent overriding a fact it had retrieved with a guess it generated. If your RAG/research agent ever "improves" on a document it just pulled, this is that bug, isolated.
2. **For comprehension, topology is a lever orthogonal to model size.** The same model that falls for the decoy trap stops falling for it when you give a *dedicated* agent one job — falsify hypotheses — and keep the exploration mechanics out of its context. A bigger model can also get there (Claude Fable 5 did) — but the role-split fixed models that fail solo, and did it with a *weaker* model in the reasoning seat. That's the planner/executor pattern, with a sharp, measurable reason it works here: doing the investigation instills a pull toward the obvious reading; an agent that *only* reasons — and never investigates — doesn't pick it up. (And it isn't merely a clean-context trick: a single agent with clean context that still explores falls anyway.)
3. **Bottlenecks are layered.** Fixing comprehension surfaced an exploration-coverage problem you couldn't see before. Expect to find the next wall behind the one you just removed.
4. **Watch your judge, and your `grep`.** The flashy failure modes are real, but a noisy LLM grader and an accent-sensitive search quietly moved more points than anything else. Rigor is the product.

## What's next

- Replicate the comprehension result on a different case (kill the single-case caveat).
- A "naming-completeness" pass so the duo stops leaving named-but-unidentified actors on the table.
- Longer-horizon cases, a red-team of the isolation, and non-Anthropic models in the same harness.

The setup is a board game. The findings aren't about board games — they're about the two ways agents fail at thinking, and the surprising news that the harder one might be something you can wire around.

---

*A note on models: I used Anthropic's models throughout — as examples, and for practicality, because they gave me a clean capability ladder to vary, topped by Claude Fable 5 (the strongest player here). Claude Fable 5 was available when these runs were done and no longer is. The findings are about agent topology, not any one vendor or model; the same harness would run others.*

*A note on the game: the case comes from [Sherlock Holmes Consulting Detective: Baker Street Irregulars](https://www.spacecowboys-games.com/game/the-baker-street-irregulars/), published by Space Cowboys. It's a commercial product, so I paraphrase its material rather than reproduce it, and quote only the agents' own reasoning.*
