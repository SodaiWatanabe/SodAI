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

Provider migration does not require changing conversation, credit, or feedback
foreign keys: those future tables should reference `app.users.id`. A new provider
identity must be explicitly linked to the existing SodAI UUID during migration;
email addresses are never used as an automatic identity-linking key.

## Model contract

Public model IDs are opaque, immutable API identifiers. The current catalog uses
`hina` as the guest default and `asuka-1` as the authenticated default. Omitting
`model` resolves through the same principal-aware policy. API requests and
`inference_runs.requested_model` store the selected public ID; the separately
versioned `resolved_model` records the concrete provider runtime. Additions start
in `app.domain.model_catalog` so metadata, audience rules, contextual defaults,
and runtime resolution do not drift across endpoints.
