# Step 5 — Gym setup and member onboarding

Implemented on 2026-10-19. This is the local implementation and verification boundary; production deployment and real email delivery are separate release operations. Step 6 payment submission, bank verification and entitlement activation are not included.

## Delivered

- Gym-only **Gym setup** navigation for owners/admins, using the shared Volt components and responsive layout.
- Public gym name, description, address, contact phone and logo, with a registration availability switch.
- Gym plans for 1, 3, 6 and 12 months; per-trainer PT plans for those durations or one session. Prices are positive integer paise, with no automatic renewal. Each plan carries explicit terms and an availability flag.
- Deliberately configured public trainer names. Private trainer account emails and relationship identifiers are excluded from the anonymous catalogue. Trainer revocation immediately removes that trainer's offerings and prevents new selection.
- Owner-only payment recipient, UPI ID and QR changes, with a preview/confirmation screen. Admins can manage branding and catalogues but cannot change the payment destination. Every saved configuration has an actor, timestamp and revision in the audit log.
- Permanent random registration UUID, shared `/join/{uuid}` link, downloadable high-contrast QR PNG and A4 reception PDF. Renaming the gym preserves its identifier. Printed materials explicitly identify a registration QR, not a payment QR.
- Mobile-friendly anonymous discovery, existing-account sign-in, and personal account creation without creating a coach or business. Email verification is required before submitting a registration. Verification and resend emails return to the intended gym, including across devices.
- A pending registration creates an active identity relationship only. It does not claim an existing coaching profile by matching email, grant staff privileges, create a paid membership/PT entitlement or reserve trainer capacity. Inactive relationships cannot be reactivated through public joining.
- Gym plan selection with an optional PT plan. A duration-based PT plan cannot exceed the selected gym duration. Exact paid dates, capacity and appointment eligibility remain Step 7 activation rules.
- Frozen plan prices, terms, trainer references, recipient, UPI ID and QR reference on each pending purchase. Total is calculated on the server. No client-supplied amount is trusted.
- Revision conflicts require refresh and review. Explicit refresh creates a replacement purchase and supersedes the old record; it never rewrites its snapshot. The database prevents snapshot modification/deletion. Members see their own history; gym admins see the latest 100 registrations in their business.
- Unknown, paused, inactive and software-subscription-unavailable registration states. Public onboarding is open only for active gyms with active, legacy or grace software access; pending/read-only businesses cannot accept registrations. Existing purchase history stays readable through the authenticated public-link history endpoint.

## Storage and transaction choices

Flyway **V9__gym_setup_onboarding.sql** adds `gym_profiles`, `gym_assets`, `gym_setup_audit`, `gym_pending_purchases`, and the optional gym return identifier on `identity_actions`.

Small public branding/payment images are stored in PostgreSQL, independently of private coaching media. Images are limited to 2 MB and 64–4096 pixels per side, at most 8 megapixels. The server decodes only single-frame PNG/JPEG, composites transparency onto white, strips metadata and trailing content, and re-encodes PNG. Uploads are bounded to 30 per gym/hour. Draft images require gym admin access; published image revisions remain accessible so historical payment instructions do not break. Image validation does not prove bank ownership; the owner must inspect the destination before confirming it.

Gym mutations and joining serialize on the gym profile. A revision check prevents stale admin overwrites and stale member consent. Request UUIDs make retries idempotent, with a payload hash preventing reuse for a different submission. Replacement ownership, relationship state, current trainer role and software access are checked in the transaction. No automatic asset cleanup removes historical QR images.

The public registration identifier is stable, but the deployment must also preserve the public domain/base URL used on printed posters. Do not use temporary preview URLs for production prints.

## API surface

| Endpoint | Access |
| --- | --- |
| `GET /gym/setup`, `PUT /gym/setup` | Selected gym owner/admin; writes require operational software access |
| `POST /gym/assets/{logo\|payment_qr}` | Gym admin for logo; owner for payment QR |
| `GET /gym/assets/{uuid}` | Selected gym owner/admin, including draft previews |
| `GET /public/gym-assets/{uuid}` | Published images only |
| `GET /public/gyms/{uuid}` | Anonymous, explicit public field allowlist |
| `POST /auth/register-member` | Rate limited; requires an available gym identifier; queues verification |
| `POST /public/gyms/{uuid}/join` | Verified identity, consent, current revision, server-side validation |
| `GET /public/gyms/{uuid}/purchases` | Authenticated identity's own active relationship only |
| `GET /member/gym-registrations` | Own history in selected business |
| `GET /gym/registrations` | Selected gym owner/admin |
| `GET /gym/registration/qr.png`, `.../poster.pdf` | Selected gym owner/admin |

## Verification

- **Passed:** frontend ESLint and TypeScript/Vite production build (335.00 kB JS, 96.94 kB gzip).
- **Passed: 80 backend unit tests**, including price/duration validation, safe image normalization, transparent images, QR decoding, member signup boundaries and verification email destination.
- **Passed: 86 disposable PostgreSQL/Flyway tests**, plus a final focused rerun of all **14 Step 5 database tests** after persistence cleanup, including V8-to-V9 upgrade, tenant and role boundaries, pending/read-only software gating, inactive relationships, duplicate concurrent submissions, concurrent replacements, immutable history, cross-tenant assets/trainers, PT duration checks, private drafts, HTTP authentication and account verification/resend.
- Real API browser exercise against a disposable database: existing member sign-in, gym/PT selection, pending submission, member workspace, owner registration list, catalogue update and rename, unchanged printed-link identifier, stale snapshot warning, and explicit replacement with retained history.
- New-account mobile browser exercise: personal signup, verification gate, synthetic verification link consumption, return to the same gym and successful pending registration. No email provider was invoked.
- Desktop, 390 px mobile and 320 px narrow-screen overflow checks. The reception PDF was rendered and inspected, and its rendered QR decoded back to the exact registration URL.

Commands run from the relevant application directory, except the database suite from the repository root:

```bash
# mobility-ai-service/
venv/bin/python -m unittest discover -s tests -v
# repository root, disposable Docker resources only
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python -m unittest discover -s database/tests -v
# vectra-ui/
npm run lint
npm run build
```

## Release order and boundaries

1. Install updated backend requirements (`qrcode[pil]`, `reportlab`; Pillow supplies image validation).
2. Apply Flyway through V9 before starting the updated API **and email worker**. The worker now reads the optional gym-return field.
3. Configure `PUBLIC_WEB_BASE_URL` to the stable HTTPS frontend origin (HTTP localhost is allowed for development). Keep the existing ACS sender and shared authentication secret configuration.
4. Deploy the frontend with `public/staticwebapp.config.json` so direct `/join/{uuid}` visits reach the React application on Azure Static Web Apps.
5. Activate the gym's software subscription under Step 4, configure its catalogue and payment destination, then enable registration and print the poster.

No production database, external provider, live payment or real email recipient was used in verification. Existing Razorpay/ACS live integration release gates remain. The new registration flow deliberately ends at an unpaid pending record; Step 6 must add payment submissions, manual bank verification and atomic activation.
