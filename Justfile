test *args:
    uv run pytest tests/ {{args}}

dev:
    uv run bayesian-quiz

simulate n='20':
    uv run simulate_players.py -n {{n}}
