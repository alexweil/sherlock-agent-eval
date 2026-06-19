.PHONY: help install test play score audit clean

RUN ?= runs/demo
CASE ?= cases/toy-example
PY ?= python3

help:
	@echo "make install   # pip install -e .[dev]"
	@echo "make test      # run the scripted-solver test suite (no model needed)"
	@echo "make play      # init a run of the toy case (RUN=runs/demo CASE=...)"
	@echo "make score     # score a run (needs RUN/grades.json from a judge)"
	@echo "make audit     # leakage audit (DENYLIST=/path/outside/repo)"
	@echo "make clean     # remove runs/ and python caches"

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

play:
	$(PY) -m sherlock_eval init --case $(CASE) --run $(RUN)
	@echo "Run created at $(RUN). Play with:"
	@echo "  $(PY) -m sherlock_eval --run $(RUN) visit \"5 C\""
	@echo "  $(PY) -m sherlock_eval --run $(RUN) status"

score:
	$(PY) -m sherlock_eval score --run $(RUN)

# Leakage audit: point DENYLIST at a PRIVATE file kept OUTSIDE this repo.
# Never commit the denylist (see README §leakage audit).
audit:
	@test -n "$(DENYLIST)" || (echo "set DENYLIST=/path/to/private-denylist.txt"; exit 1)
	./scripts/leakcheck.sh "$(DENYLIST)"

clean:
	rm -rf runs/ .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
