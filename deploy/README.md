# Deploying to exe.dev

The app runs as a `systemd` unit on a single exe.dev VM. The default VM name
is `pydata-win`; override with `EXE_VM` to use your own. HTTPS is handled by
exe.dev's proxy at `https://<vm>.exe.xyz/`. For the production deployment,
`pydata.win` is pointed at `pydata-win.exe.xyz` via DNS.

The Justfile derives the GitHub clone URL from `git remote get-url origin`,
so a fork's `just exe-deploy` will clone the fork — no edits needed.

## First-time deploy

Export the quizmaster password in your shell (and optionally the VM name),
then:

```bash
export QUIZMASTER_PASS='...'
export EXE_VM='mybox'    # optional; defaults to pydata-win
just exe-deploy
```

`exe-deploy` runs `deploy/exe-setup.sh` on first boot via `--setup-script`,
which clones this repo to `/opt/bayesian-quiz`, runs `uv sync --frozen`, and
installs the `bayesian-quiz` systemd unit (listening on port 8000) with
`enabled-but-not-started` state. It then runs `exe-set-pass`, which encrypts
`$QUIZMASTER_PASS` *on the VM* with `systemd-creds` (host-bound, not
TPM-backed because Cloud Hypervisor doesn't expose vTPM), drops the
ciphertext into `/etc/credstore.encrypted/quizmaster_pass`, and starts the
service. The plaintext password never appears in exe.dev's stored setup
script or anywhere else off the VM's persistent disk.

### DNS (optional, for a custom domain)

exe.dev cannot issue wildcard certs and the apex needs an A/ALIAS record.
For example, to point `pydata.win` at `pydata-win.exe.xyz`:

- `pydata.win` → ALIAS / ANAME to `pydata-win.exe.xyz` (or A to the VM IP
  from `ssh exe.dev stat pydata-win`).
- `www.pydata.win` → CNAME to `pydata-win.exe.xyz`.
- On Cloudflare, set the cloud icon to grey for both records.

## Routine operations

All recipes honor `$EXE_VM` (default `pydata-win`).

| Goal | Command |
| --- | --- |
| Pull latest `master` and restart | `just exe-update` |
| Upload a quiz file | `just exe-quiz <slug>` (or `just exe-quiz <slug> path/to.txt`) |
| Tail logs | `just exe-logs` |
| Reboot the VM | `just exe-restart` |
| Open a shell on the VM | `just exe-ssh` |
| Destroy the VM | `just exe-rm` |

`exe-quiz` drops the file into `/opt/bayesian-quiz/quizzes/<slug>.txt`. The
quizmaster's pick page re-reads the directory on every request, so no
restart is needed.

## Rotating the quizmaster password

```bash
export QUIZMASTER_PASS='new-value'
just exe-set-pass
```

This re-encrypts under the same VM-local key and restarts the service.
