#!/usr/bin/env python3
# strategy(observation, history) is called once per turn.
#   observation — the present: current turn, scores, your last-turn duels.
#   history     — the past: every event you may see since turn 0 (the runner
#                 fetches and caches it for you). Ignore it if unused;
#                 def strategy(observation): also works.
import random


def strategy(observation, history):
    opponents = observation.get("opponent_ids", [])
    return {
        "shoot": {opponent: random.randint(0, 2) for opponent in opponents},
        "keep": {opponent: random.randint(0, 2) for opponent in opponents},
    }
