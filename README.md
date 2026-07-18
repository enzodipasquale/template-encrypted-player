# Penalty Shootout Player Template

Fork this repository to play the UBX penalty-shootout pilot with a private strategy in a public repo. Only `strategy.py.encrypted` is committed; the workflow decrypts it in memory, submits one action, and exits.

The pilot server and tournament are already configured in the GitHub Actions workflows and `runner.py`:

```text
SERVER_URL=https://ubx-server-v2-bjyekjjk3a-uc.a.run.app
TOURNAMENT_SLUG=penalty-pilot
```

## Setup

1. Fork this repository.

2. Install the local dependencies and create an encryption key:

```bash
pip install -r requirements.txt
python runner.py keygen
```

3. In your fork, create these repository secrets in Settings -> Secrets and variables -> Actions:

| secret | value |
| --- | --- |
| `PLAYER_NAME` | Your public display name on the leaderboard. |
| `GAME_TOKEN` | Fine-grained GitHub personal access token for this fork, with `Contents: Read and write`. |
| `ENCRYPTION_KEY` | The key printed by `python runner.py keygen`. |

4. Create your local plaintext strategy:

```bash
cp strategy.example.py strategy.py
```

5. Edit `strategy.py`, then encrypt and push:

```bash
export ENCRYPTION_KEY=<your encryption key>
python runner.py validate strategy.py --game penalty_shootout
python runner.py encrypt
git add strategy.py.encrypted
git commit -m "Add strategy"
git push
```

Do not commit `strategy.py`. It is ignored on purpose.

6. In the GitHub Actions tab, run `Register player` once.

After that, the UBX server triggers `Play turn` every turn. If your workflow fails or does not submit in time, the server uses a default random action for that turn.

## Strategy Function

Write one function:

```python
def strategy(observation):
    opponents = observation["opponent_ids"]
    return {
        "shoot": {opponent: 0 for opponent in opponents},
        "keep": {opponent: 1 for opponent in opponents},
    }
```

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
