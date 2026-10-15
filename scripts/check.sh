#!/usr/bin/env sh
# Runs the same checks CI would, locally (bash). Exit code is non-zero on failure.
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
fail=0

step() {
  name="$1"; shift
  printf '\n==> %s\n' "$name"
  if ! "$@"; then
    printf 'FAILED: %s\n' "$name"
    fail=1
  fi
}

cd "$root/chumnouy_api"
if [ -x .venv/bin/python ]; then py=.venv/bin/python; else py=python; fi

step "API: OpenAPI drift" sh -c "$py scripts/export_openapi.py >/dev/null && git -C .. diff --exit-code -- chumnouy_api/openapi.json"
step "API: ruff" sh -c "$py -m ruff check app tests"
step "API: pytest" sh -c "$py -m pytest -q"

cd "$root/packages/api-client"
step "API client drift" sh -c "npm run generate >/dev/null && git -C ../.. diff --exit-code -- packages/api-client/src/schema.ts"

cd "$root/apps/web"
step "Web: test" sh -c "npm test"
step "Web: build" sh -c "npm run build"

cd "$root"
if [ "$fail" -ne 0 ]; then
  printf '\nSome checks failed.\n'
  exit 1
fi
printf '\nAll checks passed.\n'
