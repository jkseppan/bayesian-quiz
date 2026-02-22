#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["httpx"]
# ///
"""Simulate up to 150 concurrent players for load testing the Bayesian Quiz."""

import argparse
import asyncio
import json
import random

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

NICKNAMES = [
    "σ Grindset",
    "Bayes Watch",
    "p < 0.05 😏",
    "NaN of Your Business",
    "Overfitting My Jeans",
    "Drop Table Players",
    "sudo guess",
    "rm -rf /doubt",
    "404 Clue Not Found",
    "Git Push --force",
    "Principal Component of Fun",
    "The Regularizer",
    "Local Minima",
    "Gradient Descent Into Madness",
    "Kernel Panic",
    "Random Forest Gump",
    "Mean Absolute Partier",
    "R² Too",
    "TensorFlo Rida",
    "Neural Nerd",
    "Deep Learner Shallow Thinker",
    "Cross-Validated",
    "Feature Enginerd",
    "Null Hypothesis",
    "False Positive Vibes",
    "Residual Error",
    "Confidence Interval: Wide",
    "Maximum Likelihood Enjoyer",
    "Bias-Variance Tradeoff",
    "Epoch Fail",
    # Pure emoji
    "🎲", "🤖", "📊", "🧠", "🦆", "💀", "🔥", "👀", "🫠", "🤡",
    "🐍", "🎯", "🍕", "🌶️", "⚡", "🧪", "🎰", "🦀", "🐐", "💅",
    "🫡", "🤓", "🏴‍☠️", "🧃", "🗿",
    # XSS / injection attempts
    '<script>alert("xss")</script>',
    '<img src=x onerror=alert(1)>',
    '<img src="javascript:alert(0)">',
    '"><svg onload=alert(1)>',
    "'; DROP TABLE participants; --",
    '<marquee>hacked</marquee>',
    '<blink>hi</blink>',
    "{{7*7}}",
    "${7*7}",
    '<iframe src="https://evil.com">',
    '<a href="javascript:void(0)">click me</a>',
    "javascript:alert(document.cookie)",
    '<div style="position:fixed;top:0;background:red">PWNED</div>',
    '<style>body{display:none}</style>',
    "\\u003cscript\\u003ealert(1)\\u003c/script\\u003e",
    # Long / weird
    "A" * 200,
    "." * 100,
    "\u200b",  # zero-width space
    "\u202esdrawkcab",  # RTL override
    "T\u0308\u0301h\u0308\u0301e\u0308\u0301 V\u0308\u0301o\u0308\u0301i\u0308\u0301d\u0308\u0301",
    "NULL",
    "undefined",
    "NaN",
    "true",
    "false",
    "[object Object]",
    "\\n\\n\\n",
    "Robert'); DROP TABLE Students;--",
    # Absurd
    "I Trained GPT On This Quiz",
    "My Prior Is Flat",
    "Frequentist Spy",
    "50% Confidence 100% Wrong",
    "μ Too Thanks",
    "σ What",
    "Whiskers On My Boxplot",
    "Outlier And Proud",
    "The One With All The Variance",
    "Actually It's Bayesian",
    "E[Fun]",
    "P(Win) ≈ 0",
    "Markov Chainsaw",
    "Posterior Probability",
    "Monte Carlo Simulation",
    "Sample Size: 1",
    "Bootstrapped My Way Here",
    "K-Nearest Party",
    "Logistic Regression Therapy",
    "Support Vector Partying",
    "Naive But Not That Naive",
    "Decision Boundary Issues",
    "Random Walk Of Shame",
    "The Curse Of Dimensionality",
    "Spurious Correlation",
    "Simpson's Paradox",
    "Benford's Law Abider",
    "Central Limit Theorem Enjoyer",
    "I Love Lamp (Distribution)",
    "My Other Car Is A Gaussian",
    "PhD Student (Send Help)",
    "Will Quiz For Food",
    "Just Here For The μ",
    "χ² Hard, χ² Furious",
    "Ctrl+Z My Estimate",
    "I Should Be Working",
    "99th Percentile Guesser",
    "Unbiased Estimator",
    "Heteroscedastic",
    "Multicollinear Mess",
    "P-Hacking My Way To Victory",
    "Bonferroni Corrected",
    "I Peaked In Stats 101",
    "Likelihood Ratio Test Subject",
    "AIC vs BIC (I Choose Violence)",
    "Degrees of Freedom: 0",
    "My Posterior Is Thicc",
    "Conjugate Prior Experience",
    "Dirichlet Process Cheese",
    "Inverse Wishart Vibes",
    "Ergodic Hypothesis",
    "Exchangeable But Not Fungible",
]

KNOWN_ANSWERS = {
    "How many years old is Python today?": 34.0,
    "How many contributors does scikit-learn have on GitHub?": 3100.0,
    "What is the mass of the Higgs boson in GeV?": 125.25,
}


def generate_nickname(index: int) -> str:
    if index < len(NICKNAMES):
        return NICKNAMES[index]
    return f"Player #{index + 1} \U0001f916"


def generate_estimate(answer: float) -> tuple[float, float]:
    if random.random() < 0.1:
        mu = answer * random.uniform(0.5, 2.0)
    else:
        mu = answer * random.uniform(0.3, 3.0)
    sigma = abs(answer) * random.uniform(0.05, 1.5)
    sigma = max(sigma, 0.1)
    return round(mu, 2), round(sigma, 2)


async def _request_with_retry(client, method, url, label, **kwargs):
    for attempt in range(5):
        try:
            resp = await getattr(client, method)(url, **kwargs)
            return resp
        except Exception as e:
            wait = 1 * 2**attempt + random.random()
            print(f"{label}{method.upper()} {url} failed ({e}), retry in {wait:.1f}s")
            await asyncio.sleep(wait)
    print(f"{label}{method.upper()} {url} failed after 5 retries")
    return None


async def run_player(player_index: int, slug: str, base_url: str, registered: asyncio.Event):
    nickname = generate_nickname(player_index)
    label = f"[Player {player_index}] "

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        resp = await _request_with_retry(
            client, "post", f"/api/register?{slug}", label, data={"nickname": nickname},
        )
        if not resp or resp.status_code != 200:
            print(f"{label}Registration failed: {nickname!r}")
            registered.set()
            return
        if "participant_id" not in resp.cookies:
            print(f"{label}Registration rejected (no cookie): {nickname!r}")
            registered.set()
            return
        cookies = dict(resp.cookies)
        registered.set()

        submitted_for_question = -1

        while True:
            try:
                async with client.stream("GET", f"/events?{slug}", cookies=cookies) as stream:
                    async for chunk in stream.aiter_text():
                        for line in chunk.strip().split("\n"):
                            if not line.startswith("data:"):
                                continue
                            try:
                                data = json.loads(line[5:].strip())
                            except json.JSONDecodeError:
                                continue

                            phase = data.get("phase")
                            qi = data.get("current_question_index", -1)
                            question_text = (data.get("question") or {}).get("text", "")

                            if phase == "question_active" and qi != submitted_for_question:
                                answer_hint = KNOWN_ANSWERS.get(question_text, 50.0)
                                mu, sigma = generate_estimate(answer_hint)
                                await asyncio.sleep(random.uniform(0.5, 5.0))
                                est_resp = await _request_with_retry(
                                    client, "post", f"/api/estimate?{slug}", label,
                                    data={"mu": str(mu), "sigma": str(sigma)},
                                    cookies=cookies,
                                )
                                if est_resp and est_resp.status_code != 200:
                                    print(f"{label}Estimate rejected: HTTP {est_resp.status_code}")
                                submitted_for_question = qi
            except asyncio.CancelledError:
                return
            except Exception as e:
                wait = 1 + random.random() * 2
                print(f"{label}SSE disconnected ({e}), reconnecting in {wait:.1f}s")
                await asyncio.sleep(wait)


async def main():
    parser = argparse.ArgumentParser(description="Simulate players for Bayesian Quiz")
    parser.add_argument("-n", "--num-players", type=int, default=20,
                        help="Number of players (max 150)")
    parser.add_argument("-s", "--slug", default="sample",
                        help="Quiz slug (default: sample)")
    parser.add_argument("-u", "--base-url", default=DEFAULT_BASE_URL,
                        help=f"Base URL of the server (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--stagger", type=float, default=0.05,
                        help="Seconds between player joins")
    args = parser.parse_args()

    num_players = min(args.num_players, 150)
    print(f"Registering {num_players} players...")

    events = []
    tasks = []
    for i in range(num_players):
        ev = asyncio.Event()
        events.append(ev)
        tasks.append(asyncio.create_task(run_player(i, args.slug, args.base_url, ev)))
        await asyncio.sleep(args.stagger)
        await ev.wait()
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{num_players} registered")

    print(f"All {num_players} players registered and listening for questions.")
    print("Use the quizmaster panel to advance phases. Press Ctrl+C to stop.")
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\nShutting down...")
        for t in tasks:
            t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
