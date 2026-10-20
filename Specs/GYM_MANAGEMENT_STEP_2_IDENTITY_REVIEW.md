# Step 2 — identity and sessions, slice 1

Status: implemented and locally verified. The user subsequently authorized all remaining Step 2 slices; see [the completion report](GYM_MANAGEMENT_STEP_2_REVIEW.md). This document records the earlier slice-1 boundary. This is the next slice authorized after Step 1. No database migration, deployment or frontend change in this slice.

## Behavior

Authentication establishes the user identity independently of a coach profile. An existing account without a coach can sign in and restore its session at `/auth/me`; its coach field is null. The legacy coaching endpoints still require a coach and return 403 for these identities. No new public member/staff registration or automatic coach creation was added. Existing independent-coach signup remains supported.

Sign-in, signup, legacy `/login` and `/auth/me` retain the existing response fields and add `organizations`. Each entry includes organization ID/name/type, relationship ID, current unrevoked staff roles, and the explicitly linked client ID (nullable). Only active businesses and active user relationships are included. A relationship can have no staff roles and still retain its member/client link. The link describes identity, not paid membership eligibility. Unclaimed clients are never matched by name or email.

The repository reads these summaries afresh, using the authenticated user ID as its parameter. Tokens do not carry business selections or role grants. A later session request sees revoked roles or disabled relationships without requiring another sign-in. This slice does **not** yet enforce those roles on coaching operations: a coach-profile guard remains in place until slice 2. A business ID or session response must never be treated as authorization on its own.

The identity endpoint uses the bearer Authorization header only. The existing coach-only dependency temporarily accepts query tokens for compatibility with current photo/PDF clients; this compatibility still applies to all routes using that dependency, not solely downloads. When a header is present, it takes precedence and an invalid header cannot fall back to a query token. Slice 2 must replace URL credentials with authenticated media retrieval and check ownership, then remove compatibility. No frontend download behavior changed here.

Token validation rejects malformed subjects, non-positive/out-of-range IDs, malformed or timezone-free expiry, expired/tampered tokens, non-object payloads and oversized input before identity lookup. Existing issued tokens with integer subjects remain compatible when the signing secret is unchanged. Session responses expose only the public user fields, never password hashes.

## Configuration and session limits

`AUTH_TOKEN_SECRET` is now required and must contain at least 32 non-padding characters. There is no shared development fallback. Use a unique cryptographically random value in local settings or the deployment secret store. The example now leaves this value blank; actual settings and secrets were not read or changed. Missing/short values deliberately prevent API startup. Length validation does not guarantee entropy.

`AUTH_TOKEN_EXPIRATION_HOURS` must be a positive integer; its default remains 24. Coordinate all API instances on the same secret. Replacing an existing secret invalidates its tokens, so users must sign in again. No secret is generated into source control.

The existing signed-token format is retained. This slice does not introduce refresh tokens, per-session logout/revocation storage, email verification, password recovery or new account-provisioning flows. Current browser logout behavior is unchanged. Those capabilities must not be implied by the new identity context.

## Verification and review

Passed on 17 October 2026:

- 48 backend tests, including new identity/config/token tests and ASGI requests exercising `/auth/me` and the coach-only boundary. Route tests suppress local settings and external service construction.
- One targeted real PostgreSQL/Flyway integration scenario: multi-business identity, claimed member + trainer, role revocation retaining member/other-business context, inactive relationship/business filtering, and unknown-user isolation.
- Python syntax and whitespace checks.

The database scenario uses a disposable local PostgreSQL instance, synthetic legacy data and migrations through V5. No existing application database or external settings are used. No new migration was added; the complete 34-test Step 1 database suite passed at the preceding checkpoint and was not repeated for this read-only query addition. No UI changes, so frontend lint/build does not apply.

Review checked response compatibility, null coach serialization, absence of password material in the response, parameterized identity lookup, current-role filtering and separation between identity and authorization. Deployment, real browser journeys and actual production data remain unverified.

## Next slice and rollout boundary

Slice 2 must enforce current relationships/roles for all protected resources, assignment/member visibility, business-scoped repository use, queues and media. It must adapt V5's independent-coach provisioning trigger before creating gym staff profiles. Slice 3 then adds the web business selector/navigation and clears or namespaces cached state.

This backend requires the Step 1 schema through V5. Before rollout, configure the signing secret and rehearse migration/application order from the Step 1 review. Do not deploy merely because tests pass: endpoint/media authorization is unfinished. Rollback must retain the Step 1 quarantine filters and avoid restoring the shared development secret fallback. No push, merge or deployment was performed.
