# Self-hosted CI runner

GitHub-hosted Actions on private repos is blocked by account billing, and
self-hosted runners are **free** (no billed minutes). This runs the CI jobs
(`.github/workflows/ci.yml`) on your own machine.

The workflow defaults to this runner: `runs-on: ${{ vars.CI_RUNNER || 'self-hosted' }}`.

## One-time setup

1. Register the runner (needs admin on the repo). Grab a **registration token**
   (valid ~1 hour):

   ```powershell
   gh api -X POST repos/somvannda/chumnouy/actions/runners/registration-token --jq .token
   ```

2. Put it in `ci/.env` (gitignored) and start the runner:

   ```powershell
   "RUNNER_TOKEN=<paste-token>" | Set-Content ci\.env
   docker compose -f ci/docker-compose.runner.yml up -d
   ```

   For a long-lived runner, create a fine-grained PAT with the `Administration`
   (repo) permission and set `ACCESS_TOKEN=<pat>` instead of `RUNNER_TOKEN`; the
   container then mints its own registration tokens.

3. Confirm it registered (should show `online`):

   ```powershell
   gh api repos/somvannda/chumnouy/actions/runners --jq '.runners[] | {name, status, busy, labels: [.labels[].name]}'
   ```

CI now runs on this runner. To go back to GitHub-hosted runners, set the repo
variable `CI_RUNNER=ubuntu-latest`:

```powershell
gh variable set CI_RUNNER --body ubuntu-latest
```

## Notes

- The runner image (`myoung34/github-runner`) includes Git; `actions/setup-python`
  and `actions/setup-node` install the toolchains the jobs need.
- Stop it with `docker compose -f ci/docker-compose.runner.yml down`; remove it
  from the repo via GitHub → Settings → Actions → Runners.
- One machine, many repos: run one container per repo (same image, different
  `REPO_URL`/`RUNNER_NAME` and its own `ci/.env`).
- The local gate (`scripts/check.ps1` / `scripts/check.sh`) mirrors CI and is
  useful as a pre-push check and when the runner is offline. Enable the hook once
  with `git config core.hooksPath .githooks`.
