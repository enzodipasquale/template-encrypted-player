#!/usr/bin/env python3
import random


def strategy(observation):
    opponents = observation.get("opponent_ids", [])
    return {
        "shoot": {opponent: random.randint(0, 2) for opponent in opponents},
        "keep": {opponent: random.randint(0, 2) for opponent in opponents},
    }
