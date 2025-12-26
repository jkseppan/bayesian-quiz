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
LOBBY → QUESTION_ACTIVE → SHOW_DISTRIBUTION → REVEAL_ANSWER → LEADERBOARD → (next question or END)
```

1. **LOBBY**: QR code displayed, players join, quizmaster waits for enough players
2. **QUESTION_ACTIVE**: Question displayed, countdown running, players submit estimates
3. **SHOW_DISTRIBUTION**: Timer ended, show aggregate of all guesses (correct answer still hidden)
4. **REVEAL_ANSWER**: Show correct answer, fun fact, top scorers for this question
5. **LEADERBOARD**: Show cumulative standings
6. Repeat from step 2, or if last question → final leaderboard + prize announcement

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

Use HTMX to replace parts of the page from fragments sent in SSE.

The user may reload the page at any time (e.g. if they suspect their SSE connection is down) and the page must show the exact same contents as if built through the SSE replacements.

### State Sync
All clients should see the same state. Quizmaster actions trigger state transitions that broadcast to projector and all participants.

### Mobile Considerations
- Large touch targets (44px minimum)
- No hover states relied upon
- Input modes: `inputmode="decimal"` for number inputs
- Viewport-aware layouts

## File Structure (Mockups)

```
mockups/
├── index.html        # Navigation hub
├── projector.html    # Light mode, 5 screens (welcome, question, distribution, reveal, leaderboard)
├── participant.html  # Adaptive mode, 6 screens (register, waiting, question, submitted, result, winner)
└── quizmaster.html   # Dark mode, control panel
```

## Future Ideas

- Multiple distribution types (log-normal, beta, etc.)
- Team mode
- Custom question sets / JSON import
- Historical score tracking
- "Wisdom of the crowd" — show how group median compares to correct answer
- Calibration stats — are participants generally overconfident or underconfident?
