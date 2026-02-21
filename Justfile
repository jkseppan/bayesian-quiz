test *args:
    uv run pytest tests/ {{args}}

dev:
    uv run bayesian-quiz

simulate n='20' url='http://127.0.0.1:8000':
    uv run simulate_players.py -n {{n}} -u {{url}}
