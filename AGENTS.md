# Working Agreement

Mirrors the Chmaba POS working agreement so the same habits carry over.

## Git workflow (mandatory)

The default branch is `main`. Never commit to `main` directly — all work lands on
`main` through a pull request. Green CI is the gate.

### Start of every unit of work

1. `git fetch origin`
2. Branch off the latest `origin/main`:
   - `git switch -c <type>/<short-description> origin/main`
   - `<type>` ∈ `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `release`
3. Do the work on that branch only.

### While working

- Small, focused, logically grouped commits.
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`.
- Never commit secrets or generated noise. Regenerate committed artifacts
  (`chumnouy_api/openapi.json`) and commit them with the change.
- Alembic: chain `down_revision` to the single head (`alembic heads` shows one).

### Finishing

1. `git push -u origin <branch>`
2. Open a PR against `main` (`gh pr create`).
3. Wait for CI (API + Web) to pass.
4. Merge when green; delete the branch.
5. `git switch main && git pull --ff-only`.

## Repository layout

- `chumnouy_api` — FastAPI backend, source of truth for tickets, tenancy, keys.
- `apps/web` — the agent console and workspace admin. Agents operate tickets here.
- `packages/ui` — `@chmaba/ui` design tokens; every surface must use them so the
  look matches Chmaba POS. Do not hard-code a palette.
- `packages/api-client` — generated from `openapi.json`; never hand-edit.

## Product boundary

Chumnouy owns the **support/ticket domain** and the notification-free parts of it.
It does **not** own outbound notification delivery — that is Notifyr. When a
ticket event needs to reach a human, Chumnouy calls the Notifyr API; it never
implements its own email/SMS/Telegram transport.
