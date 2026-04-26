test *args:
    uv run pytest tests/ {{args}}

dev:
    uv run bayesian-quiz

simulate n='20' url='http://127.0.0.1:8000':
    uv run simulate_players.py -n {{n}} -u {{url}}

upload-quiz slug file='':
    railway variable set --stdin "QUIZ_{{slug}}" < {{ if file == '' { "quizzes/" + slug + ".txt" } else { file } }}

# --- exe.dev deployment (see deploy/README.md) ---
# VM name is configurable: `export EXE_VM=mybox` or pass via Justfile var override.
# Repo to clone is derived from `git remote get-url origin` so forks deploy themselves.

vm := env_var_or_default("EXE_VM", "pydata-win")

exe-deploy:
    #!/usr/bin/env bash
    set -euo pipefail
    : "${QUIZMASTER_PASS:?set QUIZMASTER_PASS in your shell first (only used to provision the credential, never sent to exe.dev metadata)}"
    repo_url=$(git remote get-url origin | sed -E 's|^git@github.com:|https://github.com/|; s|\.git$||').git
    {
        head -1 deploy/exe-setup.sh
        printf 'export REPO_URL=%q\n' "$repo_url"
        tail -n +2 deploy/exe-setup.sh
    } | ssh exe.dev new --name {{vm}} --setup-script /dev/stdin
    ssh exe.dev share port {{vm}} 8000
    ssh exe.dev share set-public {{vm}}
    just exe-watch-setup
    just exe-set-pass

exe-set-pass:
    #!/usr/bin/env bash
    # Encrypts $QUIZMASTER_PASS *on the VM* with systemd-creds (host-bound),
    # writes the ciphertext to /etc/credstore.encrypted/quizmaster_pass, and
    # restarts the service. The plaintext never lands on disk.
    set -euo pipefail
    : "${QUIZMASTER_PASS:?set QUIZMASTER_PASS in your shell first}"
    printf '%s' "$QUIZMASTER_PASS" | ssh {{vm}}.exe.xyz '
        sudo systemd-creds encrypt --name=quizmaster_pass - - \
            | sudo tee /etc/credstore.encrypted/quizmaster_pass >/dev/null
        sudo chmod 600 /etc/credstore.encrypted/quizmaster_pass
        sudo systemctl restart bayesian-quiz
        sudo systemctl is-active bayesian-quiz
    '

exe-watch-setup:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Waiting for exe-setup to finish on {{vm}}..."
    until ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new {{vm}}.exe.xyz \
        'state=$(systemctl show exe-setup --property=ActiveState --value); [ "$state" != "activating" ]' 2>/dev/null; do
        sleep 3
    done
    ssh {{vm}}.exe.xyz 'sudo journalctl -u exe-setup --no-pager -n 200'
    ssh {{vm}}.exe.xyz 'sudo systemctl is-failed exe-setup --quiet && { echo "*** exe-setup FAILED ***"; exit 1; } || echo "*** exe-setup completed ***"'

exe-update:
    ssh {{vm}}.exe.xyz 'cd /opt/bayesian-quiz && git pull && uv sync --frozen && sudo systemctl restart bayesian-quiz'

exe-quiz slug file='':
    scp {{ if file == '' { "quizzes/" + slug + ".txt" } else { file } }} {{vm}}.exe.xyz:/opt/bayesian-quiz/quizzes/{{slug}}.txt

exe-logs:
    ssh {{vm}}.exe.xyz 'journalctl -u bayesian-quiz -f'

exe-restart:
    ssh exe.dev restart {{vm}}

exe-rm:
    ssh exe.dev rm {{vm}}

exe-ssh:
    ssh {{vm}}.exe.xyz
