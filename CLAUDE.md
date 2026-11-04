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

### 2026-11-05 (session 6 — Dedup audit + finish inheritance fix + crosscheck UI grouping)
- **Extraction audit findings** (`scratchpad/audit_extraction.py`, `scratchpad/audit2.py`):
  - W1848L/R root cause: DESIGN has W1842L/R (42" height), ORDER has W1848L/R (48" height) — genuinely different SKUs, real discrepancy. Extraction is correct. EXTRA classification is correct.
  - FLTSHF24: DESIGN has only FLTSHF36 (page 21, Display 7). ORDER/ACK have FLTSHF24 ×3. This is likely a real discrepancy or a different model ordered vs designed.
  - Extraction cache: all 3 docs at `f8.3.5` with OpenAI provider — cache is working correctly.
  - **Dedup bug confirmed**: `AFA56S__POS_display_6` and `UC18842L__POS_display_6` — ELEVATION wins over FLOORPLAN (correct by priority), but ELEVATION has no finish while FLOORPLAN has finish. Winner drops finish info.
  - `B24BP__POS_display_4` — FLOORPLAN pos='Display 4: Island' qty=3, ELEVATION pos='Display 4: Island - Front' qty=1. Dedup keeps ELEVATION (qty=1), dropping FLOORPLAN count. KNOWN LIMITATION: elevation only shows front-visible cabinets; total count requires FLOORPLAN or SCHEDULE. No fix applied — quantity from elevation view is what the drawing shows from that angle.
- **`_dedup_view_types` finish inheritance fix** (`backend/app/engines/matching.py` lines 117–145): After winner selection (highest view_type priority), winners with no finish/door_style now inherit from dropped lower-priority items. Dedup key unchanged (display number only). The `with_finish if with_finish else same_prio` same-priority tie-breaker preserved to prevent AMBIGUOUS_DUPLICATE. 1 new regression test (`test_elevation_winner_inherits_finish_from_dropped_floorplan`). All 13 dedup tests pass.
- **UI SKU grouping in crosscheck matrix** (`frontend/src/components/crosscheck/crosscheck-list.tsx`): rewritten to group match groups by `canonical_sku`. Single-group SKUs render as before. Multi-group SKUs (TUKT ×15, SM96 ×8, QR96 ×7, etc.) collapse into an expandable row showing dominant status badge, group count, and status breakdown pills. Added `SkuGroupHeader` and `StatusBadge` components, `nested` prop on `MatchGroupCard` for styling.
- **Known gap — finish loss for some ELEVATION winners**: `AFA56S` and `UC18842L` ELEVATION winners now inherit finish correctly. Items still at risk: any ELEVATION that appears at a different normalized position than its FLOORPLAN counterpart (since they'd get different dedup keys and both survive — and the ELEVATION with no finish and no FLOORPLAN dropped-sibling remains blank). Mitigated by the fact that most ELEVATION rows in real drawings have finish or inherit it from the section header at extraction time.
- **OpenAI credits exhausted** (session context): `sk-proj-elZ9P5...` has no remaining credits; Gemini fallback is active for new extractions. User needs to add credits to re-enable OpenAI primary.

### 2026-11-04 (session 5 — Phase 3 Matching Fix + Rescan Button + Report Redesign)
- **Phase 3: FLOORPLAN+ELEVATION double-count fix** (`matching.py`): Added `_VIEW_TYPE_PRIORITY` dict and `_dedup_view_types()` function. Called at the top of `aggregate_document_items()`. Within the same display + SKU, keeps only the highest-priority view_type (SCHEDULE > ELEVATION > FLOORPLAN > LEGEND). Dedup key is `norm_sku + display_key` only — intentionally excludes finish/door_style because FLOORPLAN headers carry inherited finish while ELEVATION rows do not, which would prevent grouping if included. Removed 11 duplicate DESIGN items on Demo Project; false MISSING count dropped 14→10, total discrepancies 98→85.
- **Phase 3 tests** (`test_f8_matching_crosscheck.py`): 5 new tests covering elevation-wins, different-displays-not-deduplicated, schedule-beats-elevation, no-view-type-passthrough, end-to-end-no-false-missing.
- **Rescan button active-job check fix** (`processing_service.py`): Changed active-job guard from `status.in_([QUEUED, VALIDATING, EXTRACTING, NORMALIZING])` to `status.notin_([COMPLETED, FAILED])`. Previously, jobs in `MATCHING`, `COMPARING`, or `GENERATING_DISCREPANCIES` were invisible to the check — concurrent Rescan clicks could race and corrupt results.
- **Rescan default changed to `force_reprocess=false`** (`projects/[projectId]/page.tsx`): Rescan now reuses cached AI extraction and re-runs normalization/matching/crosscheck only (~30s vs 2–5 min). Code fixes (matching engine, normalizer) apply on every run regardless of this flag.
- **Silent pipeline dispatch failure fixed** (`processing_service.py`): Removed `except Exception: pass` that was creating QUEUED jobs that never executed. Import of `process_project_pipeline_sync` now happens outside the try/except (import errors surface immediately). Celery fallback still wrapped — but on failure logs the error and runs the pipeline inline rather than silently doing nothing.
- **Customer-friendly PDF report redesign** (`report_service.py` — `generate_pdf_bytes`): Complete rewrite of the main PDF method. New 12-section layout: (1) Header/branding, (2) Status Banner (green/orange/red by matched % + CRITICAL count), (3) Executive Summary KPI cards (5 cards: Total, Match, Changed, Missing+Extra, Uncertain), (4) Items That Match, (5) Items That Need Attention (CHANGED + per-discrepancy rows), (6) Missing Items, (7) Extra Items, (8) Needs Confirmation (UNCERTAIN, only if present), (9) Specification Differences Summary (field-level aggregation), (10) Document Relationship Note, (11) What Should Be Done Next?, (12) Documents Reviewed. OUT_OF_SCOPE groups skipped. Plain-English labels throughout (SKU→Item Code, DESIGN→Design Drawing, CRITICAL→Action Required, etc.). All other methods unchanged.

### 2026-11-04 (session 4 — Extraction Accuracy + UI Polish)
- **Cross-Check Matrix drawer → centered card** (`match-group-detail-drawer.tsx`): same `items-center justify-center` backdrop + `max-h-[90vh] rounded-xl zoom-in-95` card as Human Review drawer.
- **Extraction accuracy overhaul** (`EXTRACTION_VERSION f8.3.4`):
  - New fields: `species`, `construction`, `drawer_box` added to all 3 extraction schemas + all 3 AI prompts (with display-header inheritance rules matching finish/door_style). CrossCheckEngine section 6 compares them 3-way (WARNING severity).
  - `view_type` (FLOORPLAN | ELEVATION | SCHEDULE | LEGEND) added to DESIGN schema + prompt; Vision prompt explicitly instructs no double-counting of floorplan/elevation instances.
  - New `design_vision_v1.py`: dedicated Vision-pass prompt for DESIGN docs — display-by-display awareness, view_type classification, no-double-count rule, 200 DPI (up from 150).
  - All new fields flow through `source_metadata` on `CanonicalLineItem` (no DB migration needed).
  - Display-scoped aggregation **reverted**: position is preserved in `source_metadata` for future display-scoped matching but NOT used in group key (would cause false MISSING findings since ORDER has no display context).
- **Known gap — display-scoped matching (Phase 3)**: Same SKU in Display 1 + Display 3 sometimes shows as false MISSING because DESIGN aggregates 2 units but ORDER has 1. Fix requires matching engine rewrite (deferred per user review).

### 2026-11-03 (session 3 — Build 3)
- **"Accept All & Download Report" button** (`review/page.tsx`): single blue CTA that bulk-accepts all non-critical discrepancies and immediately downloads the PDF report in one click. Reuses `bulkAcceptMutation` + `reportsApi.downloadPdfUrl` + `getStoredAuthToken`. No new dependencies.

### 2026-11-03 (session 2)
- **Build 2: Post-upload redirect + Review CTA** (`documents/page.tsx`, `processing-status-card.tsx`): After upload success, user is redirected to `/projects/[id]` immediately (live processing status card visible). When processing completes, status card shows "Review Discrepancies →" (green, goes to `/review`) + "View Matrix" (secondary, crosscheck).
- **Inline project creation in upload modal** (`upload-document-modal.tsx`): Added "➕ Create New Project" option in the project selector. Selecting it shows a name input; on submit, project is created via `useCreateProject` hook first, then documents upload to it. Removed `disabled={projects.length===0}` from Upload button in `documents/page.tsx`. Users no longer need a separate "Create Project" step.
- **Celery + Upstash Redis setup**: Added `ssl.CERT_NONE` SSL config in `celery_app.py` for `rediss://` URLs (required for Upstash on Windows local dev). Fixed stuck processing jobs via reset script.

### 2026-11-03 (session 1)
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
