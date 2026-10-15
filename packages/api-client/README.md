# @chumnouy/api-client

A typed, dependency-free client for the Chumnouy API. The types in
`src/schema.ts` are **generated** from the committed OpenAPI spec
(`chumnouy_api/openapi.json`); `src/client.ts` is a small hand-written fetch
wrapper over them.

## Generate

```bash
node packages/api-client/scripts/generate.mjs   # or: npm run generate
```

Regenerate whenever the API contract changes — the API repo commits
`openapi.json`, so the two stay in lockstep. The generator has no dependencies
(it just walks `components.schemas` and emits interfaces/types).

## Use

```ts
import { createClient, ApiError } from "@chumnouy/api-client";

const api = createClient({ baseUrl: "https://api.chumnouy.chmaba.com", token });

const { data } = await api.listTickets({ status: "open", limit: 25 });
const ticket = await api.getTicket(data[0].id);

// Idempotent writes: a retry with the same key returns the original response.
await api.createTicket(payload, { idempotencyKey: crypto.randomUUID() });

try {
  await api.getTicket("nope");
} catch (err) {
  if (err instanceof ApiError && err.status === 404) console.warn(err.code); // "not_found"
}
```

Errors are `ApiError` with `status`, `code` and `details`, mirroring the API's
`{ "error": { "code", "message", "details" } }` envelope.

## Scope

The client covers system, console auth, tickets, integrations/keys and admin
usage. Add methods as needed — they are thin wrappers over `request<T>`; the
generated types already cover every schema.
