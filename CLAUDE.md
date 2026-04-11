# Bayesian Quiz

A real-time pub quiz app for data scientists where participants estimate answers with uncertainty. Instead of just guessing a number, players provide a probability distribution (mean + standard deviation), and scoring rewards both accuracy and well-calibrated confidence.

## Concept

Traditional pub quizzes reward the closest guess. This quiz rewards **calibrated uncertainty** — if you're unsure, say so with a wider σ. If you're confident, a tight σ will score better *if* you're right, but penalize overconfidence if you're wrong.

**Target audience**: Data scientists, statisticians, ML engineers — people who appreciate proper scoring rules and probability distributions.

**Vibe**: Fun first, but the fun has a mathematical dimension. Statistical in-jokes welcome.

## Scoring

We use **CRPS (Continuous Ranked Probability Score)** to evaluate probabilistic predictions. Lower CRPS is better (like a loss function), so we invert/transform it to points where higher is better.

For a normal distribution N(μ, σ) and true value y:
- Being close to y is good
- Having appropriate σ is good (not too wide, not too narrow)
- Overconfidence (small σ, wrong μ) is heavily penalized

Points are normalized per-question since different questions have different units/scales.

The conversion formula is `points = 100 * exp(-CRPS / scale)` where `scale` is a per-question parameter (default 10.0) chosen to match the question's natural units.

## Distribution Types

**MVP**: Normal distribution only — participants input μ (estimate) and σ (uncertainty).

**Future**: Log-normal for strictly positive quantities, possibly others. Must remain mobile-friendly — complex distribution inputs would hurt UX.

## Three User Types

### 1. Quizmaster
The host who runs the quiz. Controls the flow, entertains participants.

**Happy path**: Just click through — advance question → show distribution → reveal answer → show leaderboard → next question.

**Interface**: Dark mode control panel. Shows current state, answer counts, timer, correct answers (hidden from projector). Minimal cognitive load during the event.

### 2. Projector
The shared display everyone sees. Connected to a projector/large screen.

**Interface**: Light mode (better for projectors). Large text, high contrast. Shows:
- Welcome screen with QR code to join
- Current question with countdown timer
- Aggregate distribution of all guesses
- Correct answer reveal with fun facts
- Leaderboard

**No sensitive info**: Never shows correct answers until revealed.

### 3. Participant
Players on their phones.

**Interface**: Adaptive light/dark mode (user choice). Mobile-first. Shows:
- Registration (pick a nickname)
- Current question with input for μ and σ
- Visual preview of their distribution
- Their results compared to correct answer
- Their position on leaderboard
- Winner celebration for top 3

## State Machine

```
LOBBY → INTRO → [QUESTION_INTRO →] QUESTION_ACTIVE → SHOW_DISTRIBUTION → REVEAL_ANSWER → QUESTION_SCORES → LEADERBOARD → (next question or END)
```

1. **LOBBY**: QR code displayed, players join, quizmaster waits for enough players
2. **INTRO**: 4 slides explaining CRPS scoring (skippable)
3. **QUESTION_INTRO** (optional): If the question has an `Intro` field, show context on projector before timer starts
4. **QUESTION_ACTIVE**: Question displayed, 30-second countdown; players submit estimates; 1-second grace period after timer expires
5. **SHOW_DISTRIBUTION**: Timer ended, show aggregate of all guesses (correct answer still hidden)
6. **REVEAL_ANSWER**: Show correct answer, fun fact
7. **QUESTION_SCORES**: Show per-question top scorers
8. **LEADERBOARD**: Show cumulative standings
9. Repeat from step 3, or if last question → final leaderboard + prize announcement

## Sample Questions

- "How many years old is Python today?" (fractional years from first public release)
- "How many projects does NumFocus sponsor?"
- "How many gigawatt-hours of electrical storage was built in the EU-27 in 2024?"
- "What is the mass of the Higgs boson in GeV?"
- "How many contributors does scikit-learn have on GitHub?"

Questions should have:
- A definitive numerical answer
- Interesting trivia potential
- Relevance to the data science community
- Varied scales (some small numbers, some large)

## Design Principles

### Visual
- **Projector**: Light mode, clean whites and grays, subtle shadows, high contrast for readability
- **Participant**: User-selectable light/dark mode, mobile-optimized touch targets
- **Quizmaster**: Dark mode, information-dense but scannable

### Typography
- Display font: Space Grotesk (modern, geometric)
- Monospace: JetBrains Mono (for numbers, code-like elements)
- Mathematical notation as decorative elements (formulas in corners)

### Color
- Primary: Indigo (#6366f1 / #4f46e5)
- Secondary: Purple (#8b5cf6 / #7c3aed)
- Accent: Cyan (#06b6d4 / #0891b2)
- Success: Emerald (#10b981 / #059669)
- Warning: Amber (#f59e0b / #d97706)
- Danger: Red (#ef4444 / #dc2626)

### Data Visualization
- Gaussian curves rendered as SVG paths
- Distribution previews update live as user adjusts σ
- Aggregate distributions show individual guess markers
- Clear visual comparison between guess and correct answer

### UX
- Slider + numeric input for σ (flexibility for different users)
- 68% confidence interval displayed ("68% chance between X and Y")
- Minimal steps to submit — don't make people think during countdown
- Celebration moments for winners (confetti, animations)

## Technical Notes

### Real-time Communication
Server-Sent Events (SSE) for pushing state changes to all clients. Simpler than WebSockets for this unidirectional broadcast pattern.

Use HTMX to replace parts of the page from fragments sent in SSE. **Use HTMX 2.0.4** — HTMX 4.x has a known SSE parser bug that breaks fragment swaps.

The user may reload the page at any time (e.g. if they suspect their SSE connection is down) and the page must show the exact same contents as if built through the SSE replacements.

### State Sync
All clients should see the same state. Quizmaster actions trigger state transitions that broadcast to projector and all participants. Max 500 concurrent SSE subscribers per game.

### Session Management
Participants are identified by a UUID stored in an httponly, SameSite=lax cookie. No login required — just pick a nickname.

### Nickname Sanitization
- NFKC Unicode normalization (collapses fullwidth chars, ligatures)
- Strip Cf category (invisible format characters: zero-width, RTL marks)
- Collapse whitespace; 64-char limit
- Case-insensitive duplicate checking

### Deployment
Environment variables:
- `QUIZMASTER_PASS` (required) — HTTP basic auth password for quizmaster
- `QUIZMASTER_USER` (default: `quizmaster`) — HTTP basic auth username
- `JOIN_DOMAIN` (default: `pydata.win`) — domain shown in QR code on projector

Run with: `uv run uvicorn bayesian_quiz:app` (see Procfile).

### Mobile Considerations
- Large touch targets (44px minimum)
- No hover states relied upon
- Input modes: `inputmode="decimal"` for number inputs
- Viewport-aware layouts

## File Structure

```
src/bayesian_quiz/
├── app.py                   # FastAPI routes, SSE endpoints, session handling
├── state.py                 # GameManager, GamePhase state machine, estimate storage
├── scoring.py               # CRPS math
├── questions.py             # RFC 822-style quiz file parser
├── static/
│   └── dist-chart.js        # SVG Gaussian curve rendering
└── templates/
    ├── base.html            # Jinja2 base (HTMX, Tailwind, fonts)
    ├── index.html           # Quiz slug entry
    ├── participant.html     # Player page (adaptive light/dark)
    ├── projector.html       # Projector display (light mode, View Transitions)
    ├── quizmaster.html      # Control panel (dark mode)
    ├── control_pick.html    # Quiz selection
    └── fragments/           # HTMX partial responses for SSE swaps
        ├── participant.html
        ├── projector.html
        ├── quizmaster.html
        └── nickname_arena.html

quizzes/
└── sample.txt               # RFC 822-style question file

tests/                       # 97+ tests (pytest)
simulate_players.py          # Load testing (up to 150 concurrent players)
```

### Quiz File Format

Questions use an RFC 822-style text format with blank-line separators:

```
Question: How many years old is Python today?
Answer: 34.0
Unit: years
Scale: 10.0
Factoid: Python was conceived in the late 1980s by Guido van Rossum.

Intro: Some context shown on the projector before the timer starts.
Question: What is the mass of the Higgs boson in GeV?
Answer: 125.25
Unit: GeV
Scale: 5.0
Factoid: Discovered at CERN in 2012.
```

`Scale` controls CRPS normalization — choose it to match the natural uncertainty of the question.
`Intro` (optional) displays context on the projector before the question timer starts.

## Future Ideas

- Multiple distribution types (log-normal, beta, etc.)
- Team mode
- Custom question sets / JSON import
- Historical score tracking
- "Wisdom of the crowd" — show how group median compares to correct answer
- Calibration stats — are participants generally overconfident or underconfident?
