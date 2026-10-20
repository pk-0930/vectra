# Step 2 — accounts, permissions and web business context

Status: all three slices implemented and locally verified. The user authorized completing Step 2 without intermediate review pauses. **Stop here; Step 3 has not started.** No push, merge, production migration or deployment was performed.

## Delivered behavior

The identity/session slice remains in place: accounts need not have a coach profile, `/auth/me` returns current active business relationships, tokens carry no role grants, and an explicit signing secret is required. See the historical [slice 1 review](GYM_MANAGEMENT_STEP_2_IDENTITY_REVIEW.md).

Every coaching route now uses an authenticated, selected-business context and request-bound repositories. `Authorization: Bearer …` is required; `X-Organization-ID` selects the business. Omitting the business header is supported only when the identity has exactly one active business. Unknown or inactive business relationships return 403. A browser-selected ID never grants access.

| Actor | Read access | Write/admin access |
| --- | --- | --- |
| Owner | All clients and coaching records in the business | Coaching, client creation, existing staff listing, admin/trainer role removal, assignment changes |
| Additional admin | All clients and coaching records in the business | Coaching, client creation, trainer-role removal and assignment changes; cannot remove admins/owners |
| Trainer | Currently assigned clients only | Assigned-client coaching edits, goals, plans, AI drafts, progress and analysis; no business administration/client creation |
| Member | Only the explicitly claimed client profile, published plans, progress and analysis | Upload own progress photos and analysis videos; no drafts, private goal notes, coaching edits or staff administration |

A staff member who is also a member can switch to **My member profile** within the same business. `X-Access-Mode: member` narrows access to the member link and does not grant staff permissions. After staff-role removal, unrelated member links and other businesses survive. Ownership cannot be removed through the role-removal endpoint, so this surface cannot remove the last owner.

Relationships, organizations, active roles and assignments are checked against the database for each protected request. The request transaction locks those authorization rows until the operation finishes; a revocation serializes with in-flight operations and takes effect on subsequent requests, including existing signed sessions. Business-bound methods check resource ownership before reads/writes. Inaccessible resource IDs return 404; disallowed operations return 403. Draft generation is rejected before invoking the AI provider when the caller is not assigned coaching staff. Draft changes/approval are serialized with a row lock and committed together with the published plan.

Database dependencies use FastAPI function scope, so commit/rollback finishes before sending a successful response. `requirements.txt` now requires at least the tested FastAPI 0.135.3 version for this API. Requests performing uploads/AI generation hold their authorization transaction for the operation; production workload/lock duration still needs rehearsal.

## Media and background processing

All PDF, progress-photo and frame routes enforce the same business/client permissions. Photo lookup uses persisted metadata. The V6 frame index ties an exact blob name to an analysis and business; ambiguous legacy references, including collisions with ownerless analyses, are not adopted. Cache-buster query suffixes are removed from metadata lookup. Files are not granted ownership by filename guessing.

New annotated frames are uploaded under their analysis ID, and the worker stores matching result references and ownership rows in its completion transaction. Foreign-business worker reads, claims, retries and completion/failure updates cannot touch the row. Completed results cannot be overwritten by late poison handling. Queue messages must include a positive integer `organization_id`; old/unscoped messages are sent to poison rather than guessing ownership. Non-retryable or unexpected errors cannot mutate a job merely because its ID appeared in an untrusted message. Terminal failures after a processing claim use the business-scoped worker adapter; poison payloads preserve business context.

The API commits a newly queued analysis before enqueueing, so workers cannot race an uncommitted row. If enqueueing fails, the queued row is retained. The explicit recovery tool `mobility-ai-service/scripts/requeue_scoped_analysis.py` verifies both business and analysis identifiers, defaults to read-only, and only enqueues verified queued rows when `--enqueue` is supplied. It does not replay arbitrary poison payloads, infer ownership, reset running jobs or alter completed results.

Reusable query-string tokens are rejected everywhere, including legacy `/jobs` routes and `/frames`. Browser media/PDF retrieval sends authorization and business headers, uses temporary object URLs, and discards/revokes them when the view or context changes. API responses carry `Cache-Control: no-store`. Access removal cannot recall bytes already downloaded by an authorized user.

## Provisioning and migration

V6 removes the implicit coach-insert business trigger. Independent-coach signup explicitly provisions its business in the coach-creation transaction. A staff profile created for an already authorized business operation does not create an independent coaching business. Existing personal identities, business mappings, client claims and coaching data remain intact. After V6, an unmapped staff coach profile is intentional: the V4 legacy-only diagnostic view can flag these profiles and their new plans because it assumes independent-coach mappings. Treat that view as legacy reconciliation evidence, not an automatic repair list; never create independent businesses for staff to silence it. Current access checks use same-business user relationships.

V6 also adds the analysis-to-business composite key and `form_analysis_assets`. Existing unique frame references are backfilled from stored results; ambiguous or ownerless references remain unavailable through the API. There is no automatic claim repair or reassignment of unresolved legacy data. V1–V5 were not rewritten.

New staff invitations, verified member linking, email delivery and recovery are Step 3/later work; they were not started. The access UI manages already established relationships and assignments. Assignments in this step control record access; they do not activate paid packages or implement Step 7 capacity rules.

## Web experience

The web shell includes a business selector, current role label, combined owner coaching/admin navigation, trainer-only client tools and a member coaching page. Staff with member links can switch between their two views. Members can read published nutrition/workout plans, download PDFs, view/upload progress photos and submit/view movement analyses. Private drafts and coaching-edit controls are absent from member views.

Client/analysis selections are kept in the mounted business workspace rather than globally persisted. Business/mode switches and logout clear or replace that state; previous legacy selection keys are removed. Pending media/download responses are discarded after a context change. Role/business context refreshes when the window regains focus; unchanged context does not reset edits or file uploads. Server checks remain authoritative regardless of navigation state.

The shared palette uses electric lime `#C5F135`, charcoal `#171A16` and off-white `#F6F7F2`, with charcoal text on lime controls for contrast. Existing sessions, reporting and other future-feature placeholders remain outside Step 2.

## Verification

Passed locally on 17 October 2026:

- **53 backend unit/ASGI tests**: identity, token validation, business context, queue validation/retry/poison boundaries, annotated-frame namespace, and existing coaching/AI/squat regressions.
- **42-test full PostgreSQL/Flyway suite**, including real HTTP authorization with actual repositories and synthetic data.
- **9-test final focused Step 2 PostgreSQL suite**, including two additional scenarios for member mode and ambiguous legacy-frame backfill: **44 distinct database scenarios covered across the runs**. Final targeted checks also verified the transaction dependency's function scope and independent-coach signup after V6.
- Frontend `npm run lint` and `npm run build`; syntax checks on 63 Python source/test files (excluding the virtual environment), and `git diff --check`.
- Browser walkthrough against a temporary synthetic-data API: owner administration screen; trainer navigation and assigned-client detail without create/admin controls; member page; switching away from a selected client and seeing cleared selection; logout. Screenshots saved outside the repository: `/tmp/vectra-step2-member.png` and `/tmp/vectra-step2-access.png`.

Database tests create disposable PostgreSQL containers and use no application database/settings. Browser fixtures verify presentation/state, while real PostgreSQL/HTTP tests verify authorization. Actual Azure Blob/Queue configuration, live AI generation, deployed browser/API connections and production-scale performance were not exercised. Existing blob-container ACLs and any previously shared external URLs must be checked separately at deployment; API authorization cannot retroactively secure a publicly exposed storage container.

## Coordinated rollout and rollback

1. Review the target schema/history, back up and rehearse on a real restored copy. Inspect existing ownership/quarantine reports and ambiguous media references. Configure a unique random `AUTH_TOKEN_SECRET` of at least 32 characters; actual secrets/settings were not edited here.
2. Stop admission of new analysis jobs and drain active workers before cutover. Inventory any remaining old-format messages; they will not be accepted by the new worker. Use verified database ownership and the recovery tool for queued records rather than blindly replaying poison messages.
3. Apply migrations through V6, then deploy the matching API/worker and web bundle together. The code requires V6; an old API after V6 would not automatically provision businesses for new coach signups. Old web media links containing query tokens no longer work and must not be retained as a compatibility fallback.
4. Verify owner/admin/PT/member behavior, revoked-role sessions, business switches, uploads, scoped queue completion and protected downloads on the deployed environment before rollout.
5. Rollback must retain authorization and Step 1 quarantine protections. Do not revert to globally accessible legacy queries, public frame routes or the shared development secret. Schema changes are additive except removal of the implicit provisioning trigger; use a compatible application rollback or an explicitly reviewed forward repair.

Step 2 is complete at the local implementation/verification boundary. Deployment is a separate action. Step 3 remains unstarted and requires a new instruction.
