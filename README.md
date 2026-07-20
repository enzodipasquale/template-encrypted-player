# Penalty Shootout Player Template

Fork this repository to play a UBX penalty-shootout tournament with a private strategy in a public repo. Only `strategy.py.encrypted` is committed; the workflow decrypts it in memory, submits one action, and exits.

## Setup

1. Fork this repository.

2. Install the local dependencies and create an encryption key:

```bash
pip install -r requirements.txt
python runner.py keygen
```

3. Configure your fork under **Settings -> Secrets and variables -> Actions**. Add two **Variables** and three **Secrets** (they live on separate tabs):

| kind | name | value |
| --- | --- | --- |
| Variable | `SERVER_URL` | The UBX server URL for the tournament. |
| Variable | `TOURNAMENT_SLUG` | The tournament slug provided by the organizer. |
| Secret | `PLAYER_NAME` | Your public display name on the leaderboard. |
| Secret | `GAME_TOKEN` | Fine-grained GitHub token for this fork, with `Contents: Read and write`. |
| Secret | `ENCRYPTION_KEY` | The key printed by `python runner.py keygen`. |

   The URL and slug go under **Variables** (not Secrets) so you can see and fix them later; the workflows read them as `vars`.

4. Write your strategy, then encrypt and push. `strategy.py` stays local (gitignored); only the encrypted blob is committed:

```bash
cp strategy.example.py strategy.py
# edit strategy.py
export ENCRYPTION_KEY=<your encryption key>
export SERVER_URL=<server URL>
export TOURNAMENT_SLUG=<tournament slug>
python runner.py validate strategy.py --game penalty_shootout
python runner.py encrypt
git add strategy.py.encrypted
git commit -m "Add strategy"
git push
```

5. In the GitHub Actions tab, run `Register player` once.

After that, the UBX server triggers `Play turn` every turn. If your workflow fails or does not submit in time, the server uses a default random action for that turn.

## Strategy Function

Write one function:

```python
def strategy(observation, history):
    opponents = observation["opponent_ids"]
    return {
        "shoot": {opponent: 0 for opponent in opponents},
        "keep": {opponent: 1 for opponent in opponents},
    }
```

- `observation` is the present: current turn, scores, your duels from the
  last turn.
- `history` is the past: every event you are allowed to see since turn 0,
  oldest first, each shaped `{"turn", "kind", "payload", "ts"}` — every
  duel of yours, every action you submitted. The runner fetches and caches
  it for you (via GitHub Actions cache); you write no storage code, and the
  server only ever shows you events you are allowed to see. Ignore the
  parameter entirely if your strategy does not condition on the past
  (`def strategy(observation):` also works).

Directions are integers:

```text
0 = left
1 = center
2 = right
```

Your action must include every opponent in both `shoot` and `keep`.

## Observation

The server passes your strategy a private observation:

```json
{
  "turn": 3,
  "my_player_id": "your-player-id",
  "opponent_ids": ["opponent-a", "opponent-b"],
  "my_score": 4.0,
  "scores": {
    "your-player-id": 4.0,
    "opponent-a": 3.0,
    "opponent-b": 5.0
  },
  "recent_duels": [
    {
      "turn": 3,
      "duels": [
        {
          "shooter": "your-player-id",
          "keeper": "opponent-a",
          "shoot": 2,
          "keep": 0,
          "goal": true
        }
      ]
    }
  ]
}
```

`recent_duels` only includes duels involving you.

## Local Commands

```bash
python runner.py keygen
python runner.py encrypt
python runner.py decrypt
python runner.py validate strategy.py --game penalty_shootout
```

`python runner.py run` and `python runner.py register` are normally run by GitHub Actions.
