# Bayesian Quiz

A real-time pub quiz for data scientists where players estimate numerical answers with uncertainty. Instead of just guessing a number, players submit a mean (μ) and standard deviation (σ). Scoring rewards **calibrated confidence** using the Continuous Ranked Probability Score (CRPS) — being right matters, but so does knowing how sure you are.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Quick start

```sh
git clone <this repo>
cd bayesian-quiz

export QUIZMASTER_PASS=trustno1
uv run bayesian-quiz
```

Open <http://localhost:8000> in a browser. The sample quiz (`quizzes/sample.txt`) is included.

## Write your own quiz

Create a file in the `quizzes/` directory, e.g. `quizzes/myquiz.txt`.
The quiz code will be `myquiz`. For a sample, see `quizzes/sample.txt`.

Questions are defined in a vaguely rfc822-like format, separated by blank lines. Fields:

| Field | Required | Description |
|-------|----------|-------------|
| `Question` | yes | The question text shown to players |
| `Answer` | yes | The correct numerical answer |
| `Unit` | yes | Unit label shown on the answer (e.g. `years`, `GeV`) |
| `Scale` | yes | CRPS normalization factor — see below |
| `Factoid` | no | Fun fact revealed after the answer |

### Choosing Scale

`Scale` controls how harshly scores are penalized for being far off. A rule of thumb: set `Scale` to roughly the standard deviation you'd expect from a well-calibrated expert. If you expect typical answers to be within ±10 years, use `Scale: 10.0`. Smaller scale = steeper penalty for missing.

### Good questions

- Have a definitive numerical answer you can verify

## Running a quiz session

You need three browser windows or devices:

| URL | Who | What |
|-----|-----|-------|
| `http://host/control` | Quizmaster | Control panel — advance phases, see answers |
| `http://host/projector?{slug}` | Projector screen | Answer distributions, correct answers, leaderboards |
| `http://host/play?{slug}` | Each player | On their phone or laptop |

Replace `{slug}` with your quiz filename without `.txt` (e.g. `?myquiz`).

The quizmaster interface is protected by HTTP basic auth (`QUIZMASTER_USER` / `QUIZMASTER_PASS`).

### Flow

1. Open `/projector?{slug}` on the big screen — shows a QR code pointing to `/play?{slug}`
2. Players scan the QR code, pick a nickname, and wait in the lobby
3. Quizmaster opens `/control`, selects the quiz, and clicks **Start Quiz**
4. For each question:
   - Players have 30 seconds to submit their μ and σ
   - Quizmaster clicks **Advance** to show the aggregate distribution, reveal the answer, show per-question scores, and then the leaderboard
5. After the last question the final leaderboard is displayed

## Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `QUIZMASTER_PASS` | *(required)* | HTTP basic auth password for `/control` |
| `QUIZMASTER_USER` | `quizmaster` | HTTP basic auth username |
| `JOIN_DOMAIN` | `pydata.win` | Domain used to build the QR code URL on the projector |

Set `JOIN_DOMAIN` to your server's public hostname so the QR code links to the right place.

## Deploying to Heroku

```sh
heroku create
heroku config:set QUIZMASTER_PASS=yourpassword JOIN_DOMAIN=yourapp.herokuapp.com
git push heroku main
```

The `Procfile` is already configured.

## Development

```sh
just dev          # run dev server
just test         # run test suite
just simulate 20  # simulate 20 players against local server
```
