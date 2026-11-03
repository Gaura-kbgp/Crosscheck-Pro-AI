# CrossCheckPro — Project Reference

> Update this file after every feature. It is the single source of truth for future AI sessions.

## What This Is

**CrossCheckPro** (crosscheckpro.ai) is an AI-assisted three-way cabinet-order verification platform.

Cabinet dealers, designers, and manufacturers waste hours manually comparing three documents that must agree:
1. **Design** — the designer's plan (cabinet types, sizes, quantities)
2. **Purchase Order** — what the dealer actually ordered
3. **Manufacturer Acknowledgement** — what the manufacturer says they'll ship

CrossCheckPro uploads all three, runs AI extraction + cross-check, and surfaces every discrepancy with severity and suggested resolution — replacing a 2–4 hour manual process with a < 10-minute automated one.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS 4, Zustand 5, TanStack React Query |
| Forms/Validation | react-hook-form + Zod |
| Backend | FastAPI + Uvicorn, SQLAlchemy 2 (async-safe), Alembic migrations |
| Database | Supabase Postgres (with Row-Level Security policies) |
| Auth | Supabase Auth (primary) + FastAPI JWT fallback; JIT user/org provisioning on first API call |
| File Storage | Supabase Storage |
| Background Jobs | Celery + Redis |
| AI Extraction | OpenAI (primary) + Google Gemini (fallback via `_FallbackAIProvider` wrapper) |
| Email (transactional) | Supabase SMTP (auth flows) + custom SMTP via `EmailService` (reports) |
| Deployment | Render.com — `crosscheckpro-frontend` (Next.js static) + `crosscheckpro-backend` (FastAPI) |
| Dev Servers | `.claude/launch.json` — frontend on :3000, backend on :8010 |

## Critical Architecture Decisions

### 1. `NEXT_PUBLIC_*` env vars are build-time only
Next.js inlines `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` at build time. Setting them in Render's dashboard does nothing until a new build runs. When these are changed, always trigger **"Clear build cache & deploy"** on `crosscheckpro-frontend`, not just "Deploy latest commit".

### 2. CORS headers on 500 errors
Starlette routes `Exception` handlers through `ServerErrorMiddleware`, which sits **outside** `CORSMiddleware`. Unhandled 500s never get CORS headers via normal middleware. Fixed by:
- `backend/app/core/config.py` — `Settings.resolved_cors_origins` property (single source of truth)
- `backend/app/core/exceptions.py` — `_cors_headers_for(request)` helper manually adds the header on 500 responses

### 3. JIT provisioning race condition
The first authenticated API call auto-creates User + Organization rows. Concurrent requests (e.g. profile + organization fetched in parallel) both see "no user" and race to insert. Fixed in `backend/app/api/dependencies.py`: the `db.commit()` is wrapped in `try/except IntegrityError` — the loser does a rollback + re-query.

### 4. Multi-tenant isolation is per-query, not middleware
Every service method filters by `organization_id` explicitly. There is no reusable access-control layer. This makes cross-org features (invites, collaboration) risky to add — they require touching every service. **Decision: do not build cross-org features without a full audit.**

### 5. Auto-start processing (friction reduction)
`DocumentService._auto_start_processing_if_ready()` is called after every upload. Once all three required document types (DESIGN, ORDER, ACKNOWLEDGEMENT) are present, it calls `ProcessingService.start_processing()` automatically. The method swallows all exceptions — it must never fail the upload it's called from.

### 6. pydantic-settings and `.env` reloading
`.env` is loaded once at process startup. `uvicorn --reload` watches `.py` files, not `.env`. After changing `.env`, touch any `.py` file to trigger a reload, or restart the process manually.

### 7. Supabase `emailRedirectTo` must be allow-listed
Any `redirect_to` URL in Supabase auth flows must be added to **Authentication → URL Configuration → Redirect URLs** in the Supabase dashboard. Supabase silently falls back to the default Site URL for any URL not in that list (no error, no log).

## Data Model (Canonical)

```
Organization  1──* User
Organization  1──* Project
Project       1──* Document       (types: DESIGN | ORDER | ACKNOWLEDGEMENT)
Project       1──* ProcessingJob  (statuses: QUEUED | PROCESSING | COMPLETED | FAILED)
ProcessingJob 1──* Discrepancy    (severities: CRITICAL | HIGH | MEDIUM | LOW | INFO)
Discrepancy   1──* DiscrepancyReview
```

## Core Workflow (8 Steps)

1. User registers → org auto-created → role set (DESIGNER / DEALER / MANUFACTURER)
2. User creates a Project
3. User uploads Design + PO + Manufacturer Acknowledgement (single 3-dropzone modal)
4. **Auto-start**: once all 3 doc types are present, processing job is queued automatically
5. Celery worker runs AI extraction on each document (OpenAI → Gemini fallback)
6. CrossCheckService runs three-way comparison, creates Discrepancy rows
7. User reviews discrepancies in the Review page (accept / flag / override per item, or bulk-accept)
8. User generates a PDF report

## File Structure (Key Paths)

```
backend/
  app/
    api/dependencies.py     — get_current_user (JIT provisioning + race fix)
    api/v1/                 — all route handlers
    core/config.py          — Settings (CORS origins, env vars)
    core/exceptions.py      — global + unhandled exception handlers (CORS-on-500 fix)
    engines/cabinet_intelligence/  — AI extraction + matching engine
    models/core.py          — SQLAlchemy models
    services/               — business logic (one class per domain)
    tests/                  — pytest suite (test_processing.py has a pre-existing deadlock bug, do not run it standalone)
  main.py                   — FastAPI app, middleware, routers
  .env                      — secrets (never commit)

frontend/
  src/
    app/
      page.tsx              — landing page (unauthenticated) + redirect (authenticated → /dashboard)
      (dashboard)/
        dashboard/page.tsx  — dashboard with KPI cards + role-onboarding banner
        documents/page.tsx  — document list + UploadDocumentModal trigger
        projects/[projectId]/review/page.tsx  — discrepancy review (bulk-accept already built)
    components/
      dashboard/role-onboarding-banner.tsx  — role-aware first-time guide
      documents/upload-document-modal.tsx   — 3-dropzone upload (Design+Order+Ack in one pass)
    lib/
      store/auth-store.ts   — Supabase auth (signUp has emailRedirectTo fix)
      store/organization-store.ts

supabase/
  email-templates/          — branded HTML templates (paste into Supabase Dashboard → Auth → Emails)
    README.md               — instructions for applying each template

render.yaml                 — Render deployment config (frontend + backend services)
PLAN.md                     — original product plan (somewhat stale — see changelog below)
TESTING_REVIEW_FIXLIST.md   — full fix list from the P0–P4 testing review
```

## AI Provider Config

- **Primary**: OpenAI (`OPENAI_API_KEY` in `backend/.env`)
- **Fallback**: Google Gemini (`GEMINI_API_KEY` in `backend/.env`)
- Pattern: `_FallbackAIProvider` wrapper in `backend/app/engines/`; tries primary, catches exceptions, retries on secondary

## Roles

| Role | `BusinessRole` value | Meaning |
|---|---|---|
| Designer | `DESIGNER` | Creates the cabinet design drawings |
| Dealer | `DEALER` | Places the purchase order |
| Manufacturer | `MANUFACTURER` | Produces and ships the cabinets |

Each role sees role-specific onboarding copy on first login (via `RoleOnboardingBanner`), hidden once the org has any real (non-sample) project.

## Known Gaps / Do Not Touch Without Care

- `backend/tests/test_processing.py` — has a threading-lock deadlock in its test scaffolding. Pre-existing, unrelated to any feature. Do not run this test file standalone; the full `pytest` suite will hang.
- Cross-org invite/collaboration — intentionally not built. Multi-tenant isolation is per-query; adding cross-org features requires auditing every service method. See Decision #4 above.
- Production build staleness on Render — `crosscheckpro-frontend` auto-deploys sometimes lag. Use "Clear build cache & deploy" for any frontend change that involves `NEXT_PUBLIC_*` vars or critical UI.

---

## Changelog (newest first)

### 2026-11-03
- **3-in-1 upload modal** (`upload-document-modal.tsx`): replaced single-type dropzone with 3 parallel dropzones (DESIGN + ORDER + ACKNOWLEDGEMENT). Uses `Promise.allSettled` for independent per-slot error handling. Same external props interface — no caller changes needed.
- **Auto-start processing** (`document_service.py`): `_auto_start_processing_if_ready` triggers `ProcessingService.start_processing` automatically once all 3 doc types are uploaded to a project. Added test in `test_documents.py`.
- **Role-aware onboarding banner** (`role-onboarding-banner.tsx`): shown on dashboard until org has a real project; role-specific copy for DESIGNER / DEALER / MANUFACTURER.
- **Removed Processing Activity chart** from dashboard (no data to show at MVP scale).
- **Branded Supabase email templates** in `supabase/email-templates/` (reset-password, confirm-signup, magic-link, change-email, invite-user, reauthentication).
- **Confirm-signup email redirect fix** (`auth-store.ts`): added `emailRedirectTo: window.location.origin + '/login'` to `supabase.auth.signUp()` call so production emails link to production, not localhost.
- **CORS on 500 errors fix** (`exceptions.py`, `config.py`): `resolved_cors_origins` + `_cors_headers_for` — unhandled 500s now include correct CORS headers.
- **JIT provisioning race condition fix** (`dependencies.py`): `IntegrityError` catch + re-query in `get_current_user`.
- **Landing page** (`app/page.tsx`): replaced bare redirect with marketing hero + sample discrepancy preview for unauthenticated visitors.
- **OpenAI as primary AI provider**: wired via `OPENAI_API_KEY` in `.env`; Gemini remains fallback.
- **`render.yaml`**: added `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` to frontend service env vars.
