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
postgresql+asyncpg://sodai_app:<password>@localhost:5432/sodai
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
`hina` as the guest default and `asuka-1` as the authenticated default. Omitting
`answerer` resolves through the same principal-aware policy. Response requests
store the public answerer ID, while model executions separately record the
requested model, immutable artifact, and resolved runtime such as
`hina@<artifact-id>`. Additions start in `app.domain.answerers` so identity,
metadata, audience rules, defaults, and runtime routing cannot drift.

The browser never starts an execution directly. Thread writes create an immutable
input Entry, ResponseRequest, first Execution, context snapshot, and transactional
outbox together. The dispatcher publishes committed jobs to Redis, and the
projector is the only component allowed to apply runtime events to PostgreSQL and
the public WebSocket stream. Hina and the in-process Asuka stand-in use this same
path.

Generation jobs carry at most 32 recent turns and 64 KiB of Entry content.
PostgreSQL advisory locking enforces the configured guest and global active
Execution limits before Hina work is committed. Processed Redis entries and
published outbox payloads are removed because PostgreSQL is the sole Thread record.

The current realtime hub and one-time ticket store are process-local, so the
supported deployment shape is one FastAPI process. Horizontal API scaling first
requires a shared ticket store and committed-event fan-out; it must not be enabled
only by increasing Uvicorn's worker count.
