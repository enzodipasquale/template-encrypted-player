"""Private strategy logic.

Edit `strategy(state)` with your own decision-making. Keep this file out of git
history by committing only the encrypted `strategy.py.gpg`.
"""

from typing import Any, Dict

import numpy as np


def strategy(state: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """Return your shoot/keep directions for the current turn."""
    opponents = state.get("opponentsIds") or []
    count = len(opponents)

    if count == 0:
        return {"shoot": {}, "keep": {}}

    shoot_dirs = np.random.randint(0, 3, count)
    keep_dirs = np.random.randint(0, 3, count)

    return {
        "shoot": {pid: int(direction) for pid, direction in zip(opponents, shoot_dirs)},
        "keep": {pid: int(direction) for pid, direction in zip(opponents, keep_dirs)},
    }

