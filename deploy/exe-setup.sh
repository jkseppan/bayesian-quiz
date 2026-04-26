#!/bin/bash
# First-boot setup for bayesian-quiz on exe.dev (exeuntu image).
# Runs as the unprivileged `exedev` user; uses passwordless sudo for system bits.
# The quizmaster password is NOT installed here — provision it afterward with
# `just exe-set-pass`, which encrypts it via systemd-creds on the VM itself.
set -euo pipefail

JOIN_DOMAIN="${JOIN_DOMAIN:-pydata.win}"
REPO_URL="${REPO_URL:-https://github.com/jkseppan/bayesian-quiz.git}"
USER_NAME="$(id -un)"

sudo install -d -o "$USER_NAME" -g "$USER_NAME" /opt/bayesian-quiz
git clone "$REPO_URL" /opt/bayesian-quiz
cd /opt/bayesian-quiz
uv sync --frozen

sudo install -d -m 0700 /etc/credstore.encrypted

sudo tee /etc/systemd/system/bayesian-quiz.service >/dev/null <<UNIT
[Unit]
Description=bayesian-quiz
After=network.target

[Service]
User=${USER_NAME}
WorkingDirectory=/opt/bayesian-quiz
LoadCredentialEncrypted=quizmaster_pass:/etc/credstore.encrypted/quizmaster_pass
Environment=QUIZMASTER_PASS_FILE=%d/quizmaster_pass
Environment=JOIN_DOMAIN=${JOIN_DOMAIN}
ExecStart=/usr/local/bin/uv run uvicorn bayesian_quiz.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable bayesian-quiz.service
# Don't start yet — credential file doesn't exist until `just exe-set-pass`.
