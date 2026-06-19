#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single entry point for the harness: ``python -m sherlock_eval``.

    python -m sherlock_eval init --case <dir> --run <dir> [--mode faithful|guided]
    python -m sherlock_eval --run <dir> <command> [args]   # GM game commands
    python -m sherlock_eval score --run <dir>              # final scoring
"""
import sys

from . import gm, score


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "score":
        score.main(argv[1:])
    else:
        gm.main(argv)


if __name__ == "__main__":
    main()
