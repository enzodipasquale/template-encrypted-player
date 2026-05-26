#!/usr/bin/env python3
import random
import sys
import uuid

NUM_DUMMY_OPPONENTS = 4
NUM_ROUNDS = 5

def make_mock_round(turn_id, all_ids):
    """Build a round snapshot matching the server's actual format."""
    snapshot = {"_turnId": turn_id}
    for pid in all_ids:
        opponents = [o for o in all_ids if o != pid]
        snapshot[pid] = {}
        for opp in opponents:
            snapshot[pid][opp] = {
                "shoot": random.randint(0, 2),
                "keep": random.randint(0, 2),
                "outcome": random.choice([True, False]),
            }
    return snapshot

def make_mock_state(my_id, opponent_ids, turn, history):
    return {
        "turnId": turn,
        "state": history,
        "playerIds": [my_id] + opponent_ids,
        "myPlayerId": my_id,
        "opponentsIds": opponent_ids,
    }

def validate_action(action, opponent_ids):
    errors = []
    if not isinstance(action, dict):
        return [f"Expected dict, got {type(action).__name__}"]

    for key in ("shoot", "keep"):
        if key not in action:
            errors.append(f"Missing key '{key}'")
            continue
        mapping = action[key]
        if not isinstance(mapping, dict):
            errors.append(f"'{key}' should be a dict, got {type(mapping).__name__}")
            continue

        expected = set(opponent_ids)
        got = set(mapping.keys())
        if got != expected:
            missing = expected - got
            extra = got - expected
            if missing:
                errors.append(f"'{key}' missing opponents: {missing}")
            if extra:
                errors.append(f"'{key}' has unknown IDs: {extra}")

        for oid, direction in mapping.items():
            if not isinstance(direction, int) or direction not in (0, 1, 2):
                errors.append(f"'{key}[{oid}]' = {direction!r}, must be 0, 1, or 2")

    return errors

def main():
    try:
        from strategy import strategy
    except Exception as e:
        print(f"FAIL: Cannot import strategy.py: {e}")
        sys.exit(1)

    my_id = str(uuid.uuid4())
    opponent_ids = [str(uuid.uuid4()) for _ in range(NUM_DUMMY_OPPONENTS)]
    all_ids = [my_id] + opponent_ids

    print(f"Running {NUM_ROUNDS} rounds with {NUM_DUMMY_OPPONENTS} dummy opponents...\n")

    all_ok = True
    history = []
    for turn in range(1, NUM_ROUNDS + 1):
        state = make_mock_state(my_id, opponent_ids, turn, history)
        try:
            action = strategy(state)
        except Exception as e:
            print(f"  Round {turn}: CRASH — {e}")
            all_ok = False
            continue

        errors = validate_action(action, opponent_ids)
        if errors:
            print(f"  Round {turn}: INVALID")
            for err in errors:
                print(f"    - {err}")
            all_ok = False
        else:
            print(f"  Round {turn}: OK")
            history.append(make_mock_round(turn, all_ids))

    print()
    if all_ok:
        print("All rounds passed. Safe to encrypt and push.")
    else:
        print("Some rounds failed. Fix your strategy before encrypting.")
        sys.exit(1)

if __name__ == "__main__":
    main()
