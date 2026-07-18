# Penalty Shootout Game Rule

Every turn, each player shoots once against every opponent and keeps once against every opponent.

## Action

Your strategy returns two maps:

```json
{
  "shoot": {
    "opponent-id": 2
  },
  "keep": {
    "opponent-id": 1
  }
}
```

Use every opponent ID from `observation["opponent_ids"]` in both maps.

Directions:

```text
0 = left
1 = center
2 = right
```

## Scoring

For every ordered pair of players `(i, j)`, player `i` shoots against player `j`. The shot direction comes from `i`'s `shoot[j]`; the keeper direction comes from `j`'s `keep[i]`.

Each ordered pair has its own hidden 3 by 3 success-probability matrix. Shots are less likely to score when the shooter and keeper choose the same direction. If the shot scores, the shooter receives 1 point. If the shot is saved, the keeper receives 1 point.

## Observation

Your strategy receives only your private observation:

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

`recent_duels` contains recent shots involving you, either as shooter or keeper. The hidden probability matrices are never revealed.
