# Deploy

Deployment topology and configuration for Chumnouy. Planned alongside the first
runnable release (see `../docs/architecture.md` §10).

Target (single host to start):

```
browser
  -> https://chumnouy.chmaba.com        -> apps/web build (console)
  -> https://api.chumnouy.chmaba.com    -> chumnouy_api (uvicorn behind a proxy)
        -> postgres
        -> notifyr API (human-facing notification delivery)
```

Configuration lives in `chumnouy_api/.env` (`chumnouy_api/.env.example`) and
`apps/web/.env` (`apps/web/.env.example`). No secrets are committed.
