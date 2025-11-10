# Encrypted Strategy Player Template

Use this starter when you want a public repository (free GitHub Actions minutes) without publishing your real penalty-shootout logic. Only an encrypted payload lives in git; the workflow decrypts it just-in-time, submits your move, then deletes the plaintext.

## Files

- `strategy.py` – the file you edit. Keep the plaintext out of git history; commit only its encrypted twin.
- `strategy.py.gpg` – encrypted payload that the workflow decrypts on the runner.
- `bot.py` – helper CLI: `run` submits once, `encrypt` rebuilds the `.gpg` artefact and exports the secret key.
- `register.py` – run locally once to claim your player name on the server.
- `.github/workflows/play_strategy.yml` – scheduled workflow (every five minutes) that decrypts, runs, and cleans up.
- `.gitignore` – ignores `private-key.asc` artefacts and virtualenv clutter.
- `requirements.txt` – minimal dependency list (`requests`, `numpy`).

## Quick Start

1. **Create a fresh GPG key (one time)**

   ```bash
   gpg --quick-generate-key "YOUR NAME (penalty bot)" rsa4096 sign,encrypt 1y
   ```

   Remember the passphrase; you will store it as a secret.

2. **Export the private key for GitHub Actions**

   ```bash
   gpg --armor --export-secret-keys "YOUR NAME (penalty bot)" > private-key.asc
   base64 private-key.asc > private-key.asc.b64
   ```

3. **Author your strategy**
   - Edit `strategy.py` and implement `strategy(state)` just like the plain template.
   - Test locally with decrypted files present (see “Local testing” below).

4. **Encrypt it**

   ```bash
   python bot.py encrypt --recipient "YOUR NAME (penalty bot)"
   ```

   This overwrites `strategy.py.gpg` and writes `private-key.asc` + `private-key.asc.b64`. Commit **only** the `.gpg` file; keep the others secret.

5. **Clean up plaintext**

   After encrypting, stash or back up `strategy.py` outside your git history (e.g. `git restore strategy.py` before committing). Remove `private-key.asc` after copying its base64 variant into GitHub secrets.

6. **Add GitHub secrets** (in your public fork: Settings → Secrets and variables → Actions)
   - `SERVER_URL`
   - `GAME_TOKEN` – fine-grained PAT with Workflow scope (exposed as `GITHUB_TOKEN` to the job)
   - `GPG_PRIVATE_KEY_B64` – paste the contents of `private-key.asc.b64`
   - `GPG_PASSPHRASE`
   - `PLAYER_NAME` (the display name you will register)

7. **Register once**
   - Export `SERVER_URL`, `GITHUB_TOKEN`, and `PLAYER_NAME` in your terminal.
   - Run `python register.py` to create (or confirm) your player on the server.

8. **Commit and push**
   - Commit the encrypted payload and template files (not the plaintext strategy or key files).
   - Trigger “Play Strategy” manually once to confirm the decrypt → run → cleanup path.

## Register once (manual step)

Registration now happens outside GitHub Actions. After exporting the same variables you set as secrets:

```bash
export SERVER_URL="https://your-server.example"
export GITHUB_TOKEN="ghp_xxx"    # same token stored as GAME_TOKEN
PLAYER_NAME="your-visible-name"

python register.py      # register once
python bot.py run       # smoke-test a single submission
# python bot.py encrypt --recipient "YOUR NAME (penalty bot)"  # when strategy changes
```

Run `python register.py` whenever you change the display name. Keep the returned `player_id` for reference.

## Local testing

Keep `strategy.py` local-only while you experiment:

```bash
export SERVER_URL=...
export GITHUB_TOKEN=...
python bot.py run
```

Ensure the decrypted file sits next to `bot.py`. Before committing, restore or stash any changes to `strategy.py` so they do not leak into git.

## Updating your strategy

1. Edit `strategy.py` and test locally (`python bot.py run`).
2. Re-run the encryption helper (`python bot.py encrypt --recipient ...`).
3. Commit and push the new `strategy.py.gpg` (after restoring the plaintext file).

## Safety notes

- Never commit the plaintext strategy or raw private key.
- Rotate your GPG key periodically and refresh the GitHub secrets.
- Avoid printing secrets—workflow logs are visible to anyone with repo access.

Once you add your secrets and encrypted payload, the workflow will submit every five minutes without costing your students anything or exposing their tactics.
