# SodAI Backend

FastAPI owns only the PostgreSQL `app` schema. Authentication providers own their
own storage (the current Better Auth deployment uses `auth`) and communicate with
this service exclusively through signed OIDC-compatible JWTs.

## Database migration

```bash
cp .env.example .env
alembic upgrade head
```

`DATABASE_URL` must use SQLAlchemy's asyncpg form:

```text
postgresql+asyncpg://sodai_app:<password>@localhost:13203/sodai
```

## Authentication contract

The API validates the configured issuer, audience, expiration, issued-at time,
subject, signing algorithm, and JWKS key ID. A verified `(issuer, subject)` is
mapped to an immutable SodAI UUID on first access to `GET /api/v1/account/me`.

Provider migration does not require changing space, thread, credit, or feedback
foreign keys: those future tables should reference `app.users.id`. A new provider
identity must be explicitly linked to the existing SodAI UUID during migration;
email addresses are never used as an automatic identity-linking key.

## Answerer contract

Public answerer IDs are opaque, immutable API identifiers. The catalog uses
`hina` as the guest default and `asuka-1.1` as the authenticated default. Omitting
`answerer` resolves through the same principal-aware policy. Response requests
store the public answerer ID and shared `reasoning_effort`, while model executions
separately record the requested model, immutable artifact, and resolved runtime such as
`hina@<artifact-id>`. Additions start in `app.domain.answerers` so identity,
metadata, audience rules, reasoning capabilities, defaults, and runtime routing
cannot drift.

The browser never starts an execution directly. Thread writes create an immutable
input Entry, ResponseRequest, first Execution, context snapshot, and transactional
outbox together. The dispatcher publishes committed jobs to Redis, and the
projector is the only component allowed to apply runtime events to PostgreSQL and
the public WebSocket stream. Hina and the in-process Asuka stand-in use this same
path.

Human Lite, Human Standard, and Human Pro reuse the same ResponseRequest, Execution, context, and
ThreadEntry records without creating a model outbox job. Their rank-based FIFO
matching, Brain readiness lease, shared reasoning deadline, skip loop, and extension boundary are documented in
`docs/architecture/human-brain.md`.

Generation jobs carry at most 32 recent turns and 64 KiB of Entry content.
PostgreSQL advisory locking enforces the configured per-guest/model and per-model active
Execution limits before Hina work is committed. Processed Redis entries and
published outbox payloads are removed because PostgreSQL is the sole Thread record.

Failed response requests are retried with
`POST /api/v1/response-requests/{id}/executions`. The required `Idempotency-Key`
is hashed at the boundary; one key always resolves to one Execution under the
same ResponseRequest. Retry does not duplicate the input Entry or context snapshot.

The current realtime hub and one-time ticket store are process-local, so the
supported deployment shape is one FastAPI process. Horizontal API scaling first
requires a shared ticket store and committed-event fan-out; it must not be enabled
only by increasing Uvicorn's worker count.

## Credit contract

Credits use an append-only, double-entry ledger. Balances are derived from postings;
they are never updated directly. Grants create source-aware lots with optional expiry,
and metered inference reserves the catalog's maximum charge before its outbox job is
committed. Terminal projection settles the measured charge or releases the reservation
in the same database transaction as its usage record.

Hina is free for guests and authenticated users. The first valid Asuka 1.1 request while
the allowance is dormant starts a user-specific 168-hour, 20-credit lot; successful
responses settle 0.1 credit and failures release the reservation. Reading the balance or
using Hina never starts the clock. Both answerers still create immutable billing intent
snapshots and terminal usage records. The active allowance and cursor-paginated history
are exposed at `GET /api/v1/credits` and `GET /api/v1/credits/transactions`. Operational
grants and expiration use `make credits-grant` and `make credits-expire`; the complete
invariants and lifecycle are documented in `docs/architecture/credits.md`.
