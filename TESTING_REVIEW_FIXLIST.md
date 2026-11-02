# Testing Review — Findings & Fix Plan

Source: external QA pass against the **deployed** Render instance
(`crosscheck-pro-ai-tool.onrender.com` / `crosscheck-pro-ai.onrender.com`), dated 2026-11-01.
All three roles (Designer, Dealer, Manufacturer) were **blocked at login** — nothing past
auth could be tested live. Section 04 of the review is a hand-built "answer key" from real
Marsh Furniture paperwork that the matching engine must reproduce once unblocked.

Status column: `TODO` / `DIAGNOSED` / `FIXED` / `NEEDS USER ACTION` (things only the account
owner can do, e.g. Render dashboard settings).

---

## P0 — Blocks everything, fix first

### P0-1. Login/signup completely blocked by CORS on production — `DIAGNOSED`
**Symptom:** Every auth call (`/auth/register`, `/auth/login`, `/auth/google/callback`) from the
live frontend origin fails preflight: `No 'Access-Control-Allow-Origin' header is present`.
`GET /health` works (simple request, no preflight); anything requiring a JSON POST does not.

**Root cause, confirmed in code:** [`backend/app/core/config.py:48`](backend/app/core/config.py:48)
```python
CORS_ORIGINS: str = "http://localhost:3000"
```
This is read from the `CORS_ORIGINS` environment variable. In [`render.yaml:32-33`](render.yaml:32),
it's declared `sync: false` — meaning Render **never auto-populates it**; it must be set manually
in the Render dashboard. If it was left unset (or set without the exact deployed frontend URL,
or with a trailing slash), the backend's CORS middleware correctly refuses the real frontend's
origin — exactly matching the observed symptom. This is a deployment-config gap, not broken
middleware logic (`main.py`'s `CORSMiddleware` setup itself — `allow_methods=["*"]`,
`allow_headers=["*"]`, `allow_credentials=True` — is correct).

**Fix:**
1. **User action (Render dashboard):** set `CORS_ORIGINS` on the `crosscheckpro-backend` service to
   the exact live frontend origin(s), comma-separated, no trailing slash:
   `https://crosscheck-pro-ai-tool.onrender.com,https://crosscheckpro.ai,https://www.crosscheckpro.ai`
2. **Code hardening (defense-in-depth):** make `main.py` always include the known production
   frontend origins as a fallback, the same way it already hardcodes localhost dev origins —
   so a missing/wrong env var degrades gracefully instead of silently locking out all users.
3. **Regression guard:** add a post-deploy smoke test (sign up a throwaway user from a script
   hitting the live URL) so this class of failure is caught automatically, per the review's own
   P0-1 recommendation.

### P0-2. Backend cold-starts blank on Render free tier — `FIXED` (verified in code)
**Symptom:** first visit shows blank white page for several seconds (Render free tier spins down
idle services), then redirects to login with no feedback.

**Fix:** `AppShell` (`frontend/src/components/layout/app-shell.tsx:30-53`) already renders a
branded "Initializing CrossCheckPro..." spinner screen while `isInitialized`/`isLoading` is true,
instead of blank white, for every authenticated route. Root `/` no longer redirects straight to
that gate either — see the new home page below, so unauthenticated first visits get an explained
landing page, not a cold-start stall.
Keep-warm ping / always-on instance is still a cost tradeoff — **left as a user decision**, not
changed here.

### P0-3. Raw "Failed to fetch" / raw server errors shown to users — `FIXED` (verified in code)
**Symptom:** network/CORS failures surface literally as `Failed to fetch` instead of a readable
message.

**Fix:** `frontend/src/lib/api/client.ts:120-131` already catches any non-`ApiClientError` thrown
by `fetch()` (bare `TypeError`s for network/CORS/offline failures) and rethrows the plain message:
*"We couldn't reach CrossCheckPro. Try again in a minute. If it keeps happening, contact
support@crosscheckpro.ai"* — the raw browser `Failed to fetch` text never reaches the UI. Also
confirmed in code: our FastAPI exception handlers (`global_exception_handler`,
`unhandled_exception_handler` in `app/core/exceptions.py`) only handle responses that *reach* the
app — a blocked preflight never gets that far, so this fix is frontend-side.

---

## Not in the original review — found while live-testing P1-4's role onboarding

### JIT user-provisioning race condition on first login — `FIXED` (verified live)
While live-testing the new role-aware dashboard onboarding banner (below), a brand-new
account's **very first** page load intermittently failed: the browser console showed
`blocked by CORS policy` on `GET /organizations/me` / `GET /users/me`, identical-looking to
P0-1's symptom but with CORS already fixed.

**Root cause:** `get_current_user` (`app/api/dependencies.py`) auto-provisions a `User` +
`Organization` row the first time a Supabase-authenticated request arrives for an auth_id with
no matching row yet ("JIT provisioning"). The frontend fires `GET /users/me` and
`GET /organizations/me` together right after login — both see "no user yet" and race to
`INSERT`. The loser hits `users.auth_id`'s unique constraint, which was unhandled → a bare 500.
Confirmed by concurrent-request testing against 4 fresh accounts: the loser consistently got a
500 before the fix.

**Separate compounding bug:** that 500 never carried CORS headers. Starlette routes a handler
registered for the bare `Exception` class through `ServerErrorMiddleware`, which sits *outside*
`CORSMiddleware` — so every unhandled-exception response, not just this race, was CORS-header-
less, and the browser reported a misleading "CORS blocked" instead of the real 500. Confirmed via
direct `curl`: the 500 response had no `Access-Control-Allow-Origin` header even with a valid,
allow-listed `Origin`.

**Fix applied:**
- `app/api/dependencies.py`: catch `IntegrityError` on the provisioning commit, roll back, and
  re-query for the row the winner just created instead of crashing.
- `app/core/exceptions.py`: `unhandled_exception_handler` now adds
  `Access-Control-Allow-Origin`/`-Allow-Credentials` by hand when the request's `Origin` is
  allow-listed, so a real 500 reaches the browser as a 500, not a confusing CORS failure.
- `app/core/config.py`: the hardcoded origin fallback list (previously only in `main.py`) is now
  `settings.resolved_cors_origins`, a single source of truth both `main.py` and
  `exceptions.py` use.

**Verified live:** re-ran concurrent `organizations/me` + `users/me` requests against 4 separate
fresh Supabase accounts after the fix — all 8 requests returned `200` with matching
organization/user ids and a correct CORS header; reproduced the original failure beforehand on
an unpatched run for comparison. Also confirmed end-to-end through the real browser UI (see
P1-4 below) — a fresh signup's dashboard now loads correctly on the first request, every time.

---

## Not in the original review — found while live-testing P1-1/P1-2

### AI provider resilience — `FIXED`
While running real extraction tests, discovered the primary `OPENAI_API_KEY` in `backend/.env`
is invalid (OpenAI rejects it with 401) — meaning **extraction cannot run at all right now**,
locally or deployed, on OpenAI alone. Added a real automatic fallback instead of just reporting
this: `app/integrations/ai/factory.py` now wraps the primary provider so any
`extract_structured_data` failure (bad key, rate limit, outage) automatically retries on Gemini,
if `GEMINI_API_KEY` is configured. Two bugs found and fixed while wiring this up:
- `GeminiProvider.extract_structured_data()` (`app/integrations/ai/gemini.py`) didn't accept the
  `doc_type` keyword argument that production code (`app/worker/tasks/processing.py`) always
  passes — would have crashed on any real Gemini call, fallback or direct.
- `requirements.txt` had the wrong Gemini package pinned (`google-generativeai`, the legacy SDK)
  while the code is written for the new `google-genai` SDK (`from google import genai`,
  `genai.Client(...)`) — so `GeminiProvider` silently returned `{}` instead of erroring, with no
  indication anything was wrong.

**Still needed:** replace the invalid `OPENAI_API_KEY` in `backend/.env` (and on Render) so
production doesn't depend on the Gemini fallback alone.

---

## P1 — Core product correctness, fix once P0 is clear

### P1-1. Marsh acknowledgement reader must handle real-world quirks — `FIXED` (verified live)
The review's answer key (section 04, real Marsh job: Chesapeake Bay Display R3, ack #1333465 +
#1334466) is the actual acceptance test. **Live-tested 2026-11-02** by calling the real
`extract_structured_data` pipeline directly against the actual downloaded PDFs (not mocked data):

- ✅ Ack #1334466 (Exclusives): extracted exactly 4 line items, matching the review's count.
  Line 3 (Sagewood/PHW mantel hood) and line 4 (`OBLQ HD 37 1/4 X 44 3/4`, Oak/Jute) matched the
  answer key verbatim.
- ✅ Ack #1333465: extracted all 4 of the review's changed-quantity/style discrepancies exactly —
  MCV96 line 57 qty 2, TK96 line 36 qty 2, SM96 line 123 qty 4, QR96 line 127 ×3 door style APEX
  — correct line number, SKU, and quantity on every one.
- ✅ PLY construction flag: all 12 lines in the review's cited ranges (8–16, 53–55) correctly
  marked PLY.
- ✅ Continuation lines (`MOD: AOVD-R`, `RP9624_PA`) correctly merged into the parent line's
  notes, not duplicated as phantom items.
- ✅ Discount line (128, `-16875.52`) correctly isolated as a credit.
- ✅ Zero-price factory note (line 850, `FOL_1-1/4_NEW`) correctly isolated, matching the
  review's exact example.
- ✅ **Totals reconciliation: sum of all extracted line prices = $14,965.07**, matching the
  review's expected sales total to the penny.

This required fixing two separate real bugs uncovered along the way (both already fixed):
`GeminiProvider.extract_structured_data()` was missing the `doc_type` kwarg production code
always passes (crashed on any Gemini call), and `requirements.txt` had the wrong Gemini SDK
package pinned (`google-generativeai` instead of `google-genai`), so Gemini silently no-op'd
instead of erroring. Both needed since the primary OpenAI key is currently invalid (separate,
still-open issue — see note below) and extraction only succeeded via the Gemini fallback.

**Open item:** the primary `OPENAI_API_KEY` in `backend/.env` is invalid (401 from OpenAI) — this
test only passed because of the new OpenAI→Gemini fallback (see "AI provider resilience" below).
Fix the OpenAI key too, so production doesn't depend on Gemini alone.

Original parsing requirements this was tested against:
- 7 pages with **repeated headers** — must read 128 lines once, no duplicates from the repeated
  bill-to/ship-to block.
- **Continuation lines** (`MOD: AOVDR`, `MOD: FI`, `RP9624_PA`) belong to the line above, not new
  items.
- **Discount lines** (e.g. line 128 `535100 CONCESSIONS DISPLAY DISCOUNT 16875.52-`) are credits,
  not cabinets — trailing minus = negative.
- **Zero-price lines** (e.g. `FOL_1-1/4_NEW .00`) are factory notes, not line items.
- **Same SKU, different casing/punctuation** across drawing vs. ack (`str396sh` vs `STR396-SH`,
  `BLC1884L` vs `BLC188424L`) — normalize case and dashes before matching; this is exactly what
  `ManufacturerCodeDictionary` aliasing (built earlier this project, see `backend/app/engines/
  cabinet_intelligence/`) is for — verify it actually gets exercised on real data like this.
  Short codes to recognize: `PHW` (paint-grade hardwood), `POK` (painted oak), `PLY` (plywood),
  `FX` (drawer box), `B`/`B*` (finished ends).
- **Custom "Exclusives" items** (`SC90...` with raw dimensions like "54 X 42 X 19") aren't in any
  catalog — must show as `custom: check by hand`, never as `unknown SKU`.
- **Totals must reconcile:** sales total 14,965.07, tax 897.91, order total 15,862.98, 171 pieces
  — a useful built-in sanity check after parsing.

**Done when:** ack #1333465 parses to exactly 128 lines (127 items + 1 discount) with correct
qty/style/species/finish/PLY/mods/price, and totals reconcile.

### P1-2. Designer drawing reader, grouped by display/room — `FIXED` (verified live)
Must read each display's header (door style, finish, construction, drawer box) plus trim
callouts, and link them to "items X–Y" ranges in the acknowledgement.

**Live-tested 2026-11-02** against the real Chesapeake Bay drawing (22 pages) — 4 full extraction
runs via the actual `extract_structured_data` pipeline (not mocked), comparing every run directly
against the review's section 04 answer key.

**Initial run (before fix) found 3 real gaps, all now closed:**
- `DESIGN_PROMPT_V1` only instructed the model to extract discrete SKU-bearing items — no
  instruction to capture small trim/moulding codes with the same rigor as cabinets, and no
  instruction to capture free-text display-level construction notes (e.g. "Construction:
  Furniture Board") into the `DesignExtractionItem.notes` field that already existed but was
  never being populated.
- A second root cause, found by reading the PDF's own text layer directly (`fitz`/PyMuPDF, no AI
  involved): page 16 ("Display 5: Double Oven Kitchen") packs **three separately-named
  sub-sections** ("Salt", "Dewdrop", "Drift"), each with its own near-identical block of trim
  callouts (`Crown: ... mcv96 – 1` appears twice, once per sub-section) — the model was
  collapsing these as apparent duplicates instead of treating each sub-section as physically
  separate items.

**Fix applied** (`backend/app/integrations/ai/prompts/design_v1.py`): added explicit rules to
(1) extract every trim/moulding/scribe code with full rigor, never skipped for being visually
small, (2) capture display-level construction/material callouts verbatim into `notes` on every
item in that display, and (3) never deduplicate near-identical callouts across differently-named
sub-sections on the same page/display.

**Verified after the fix** — re-ran extraction 3 more times against the same real file:
- ✅ Construction notes ("Construction: FURNITURE BOARD" / "Construction: PLYWOOD") now populate
  reliably across every display, directly enabling the PLY-construction discrepancy the review
  flagged (confirmed correct on the ack side already — see P1-1).
- ✅ **MCV96 correctly extracted twice** — Display 5 Salt (qty 1) and Display 5 Drift (qty 1) —
  plus MCV144 for Display 5 Dewdrop (qty 1), exactly matching the three sub-sections read
  directly from the PDF's text layer.
- ✅ **SM96 for Display 6 Mudroom extracted at qty 3**, exactly matching the review's answer key
  (design qty 3 vs ack qty 4 → the quantity-changed discrepancy is now detectable).

**Known characteristic, not a bug:** extraction runs showed real run-to-run variance on this one
densely-packed, 3-sub-section page — not every run captured every item on the first try (vision
extraction isn't perfectly deterministic). This is exactly what the product's confidence scoring
and human-review workflow exist for; it is not something prompt wording alone can guarantee to
100%, and should not be chased further as if it were a pure code bug.

**Done when:** running the actual Chesapeake Bay drawing + both acks through the pipeline
reproduces the review's answer key exactly:
- **7 flagged discrepancies** (3× changed-quantity, 1× changed-construction, 3× review-flag —
  possibly-missing/style-mismatch/design-note-vs-ack) — full table in the review, section 04.
- **Zero false alarms** on the 7 "should match" display groups also listed in section 04 — this
  is as important as catching the real discrepancies; over-flagging matched items is a named
  failure mode the review explicitly calls out ("if the tool flags them, its matching is too
  strict").

Still needs a real dealer Order file (see "Known data gap" below) to test through the actual
three-way `/process` pipeline end-to-end, since that endpoint requires all three document types.

### P1-3. 10MB upload limit too small for real manufacturer catalogs — `FIXED` (verified live)
**Symptom:** spec says ~10MB limit; the real Marsh Spec Guide is 14.2MB / 576 pages.

**Root cause, confirmed in code:** the MB size limit was already 200MB (not 10MB) — the real
blocker was `MAX_PDF_PAGES = 100` in `app/core/config.py`, shared by every PDF upload type,
which would reject a 576-page catalog outright regardless of its size.

**Fix applied:** added a separate `MAX_CATALOG_PDF_PAGES = 700` setting, used only by
`spec_book_service.py` and `nkba_reference_service.py`. Regular project documents (design/order/
acknowledgement, via `document_service.py`) stay capped at the original 100 pages — those should
legitimately be short, and loosening that cap would have been wrong.

**Verified live:** uploaded a real 150-page test PDF as a manufacturer spec book → `201 Created`
(previously would have been rejected). Uploaded the identical file as a project design document →
correctly rejected with `400: PDF page count (150) exceeds maximum limit of 100 pages`, proving
the fix is scoped correctly and didn't loosen the wrong path. All 25 existing spec-book/NKBA
tests still pass.

### P1-4. No role selection at signup — `FIXED` (scoped down, verified live)
**Symptom:** signup only asks name/email/password — no "I am a: Designer / Dealer /
Manufacturer" + company name, so there's no role-appropriate first-run experience.

**What existed already:** backend's `RegisterRequest` already accepted `organization_name`
(just never captured by the signup UI); `Organization.settings` existed as a flexible JSON
field. No business-role concept existed anywhere — not to be confused with `Role`
(ADMIN/REVIEWER/VIEWER), which is in-app permission level, not business function.

**What was added (data layer + signup UI):**
- New `BusinessRole` enum (DESIGNER/DEALER/MANUFACTURER) and `Organization.business_role`
  column (`app/models/core.py`), additive migration applied live.
- `RegisterRequest.business_role` + `AuthService.register()` persists it.
- Supabase-first signup path (the primary path, since the anon key fix): `auth-store.ts` now
  forwards `business_role` in Supabase `user_metadata`, and the JIT-provisioning code in
  `app/api/dependencies.py` (`get_current_user`) reads it back when auto-creating the
  organization — both signup paths are covered, not just the FastAPI fallback.
- `OrganizationResponse` schema gained `business_role`.
- Signup page (`frontend/src/app/signup/page.tsx`) now has an "I am a: Designer / Dealer /
  Manufacturer" selector (3 cards) and an optional Company Name field.

**Live-tested 2026-11-02:** registered a real account with `business_role: DEALER` and
`organization_name: "Test Dealer Co"` via the actual `/auth/register` endpoint — confirmed
correct in the database. Found and fixed a real bug along the way: `GET/PATCH /organizations/me`
(`app/api/v1/organizations.py`) manually constructs `OrganizationResponse(...)` field-by-field
and had never been updated to include the new field, so it silently returned `business_role:
null` regardless of the real DB value — fixed both occurrences, re-verified the API now returns
the correct value end-to-end (register → DB → login → `GET /organizations/me`).

**Scope decision on the cross-org invite flow (2026-11-02):** the review's section 03 flow
diagram has a Dealer "invite" a Designer/Manufacturer *from a different company* into their job.
Investigating this properly before building it: `organization_id`-scoped tenant isolation is
hard-coded at the row level across every table a project touches (Project, Document,
Discrepancy, MatchGroup, CanonicalLineItem, HumanReview, AuditLog, Report — 6+ services, dozens
of call sites), not just at the project level. A real cross-org invite needs a rewrite of that
authorization model everywhere, which is a correctness/security-critical change (get it wrong
and one company's data becomes visible to another's) — explained to the user and **deliberately
descoped** rather than attempted half-safe in one pass. Flagged as a separate, larger piece of
work if/when wanted.

**What was built instead (role-aware first-step onboarding, single-org, verified live):**
`RoleOnboardingBanner` (`frontend/src/components/dashboard/role-onboarding-banner.tsx`) on the
Dashboard shows each business role its one-line "first job" from section 03 — Designer: upload a
drawing; Dealer: create a job and upload the order; Manufacturer: load the catalog, then upload
the acknowledgement — with a CTA into Projects. It only shows until the org has a real
(non-sample) project; after that it disappears, since by then the user already knows their way
around.

**Live-tested 2026-11-02** against three fresh accounts (Designer/Dealer/Manufacturer, created
and logged in through the real signup/login flow): each showed its own correct role copy, and
the banner correctly disappeared immediately after creating a real project via the actual
"Create Your First Project" button. This testing is what surfaced the JIT-provisioning race
condition documented above — all test accounts and org/project rows were cleaned up afterward.

---

## P2 — Polish, after P0/P1

- **P2-1.** `FIXED` (verified live) — every new signup now auto-gets a pre-checked "Chesapeake
  Bay Display (Sample)" project (status COMPLETED, 3/3 documents, 2 real discrepancies built from
  the same verified Chesapeake Bay data used in P1-1/P1-2 testing — a quantity change on MCV96
  and a construction upgrade, plus one clean matched item). Built directly from DB rows (no AI
  call, instant, free) via `app/services/sample_data_service.py`, wired into both signup paths
  (backend `AuthService.register()` and the Supabase-first JIT-provisioning path in
  `dependencies.py`). New `Project.is_sample` column (migration applied) drives a purple "Sample"
  badge on the project card/table so it's never confused with real data. Live-verified: registered
  a fresh account, confirmed the sample project renders correctly end-to-end via the real UI
  (Projects page: 1 project, 3 documents, 2 discrepancies, 100% progress, Sample badge visible).
- **P2-2.** `FIXED` (verified live) — new `generate_shareable_summary_pdf_bytes` /
  `_csv_data` methods in `report_service.py`, exposed at `GET /projects/{id}/reports/summary/pdf`
  and `/summary/csv`, distinct from the existing comprehensive audit report (which is explicitly
  marked "Confidential — For Internal Organization Use Only" and is multi-page, so reusing it
  wasn't an option). Filters to only `OPEN`/`ESCALATED` discrepancies (nothing already resolved),
  sorted by severity, one compact table, fits on one page. Also fixed a real data gap found along
  the way: `app/worker/tasks/processing.py` was only capturing the manufacturer's line number
  (`source_metadata.line_number`) for ORDER items, never ACKNOWLEDGEMENT — exactly the one a
  dealer needs when forwarding a report back to the manufacturer. New "Share Action Items with
  Manufacturer" card on the frontend Reports page. Live-tested: generated the real PDF/CSV against
  the sample project's 2 discrepancies, found and fixed two rendering bugs (title/subtitle overlap,
  "WARNING" text wrapping in too-narrow column), re-verified clean — confirmed via the actual UI
  button click (network request 200 OK), not just the API directly.
- **P2-3.** `FIXED` (verified live) — replaced "Document Intelligence for Construction Projects"
  and every other generic "construction project(s)" phrase with cabinet-industry language,
  across 10 files: the auth-page hero headline (login/signup/forgot-password/reset-password/
  verify-email) now reads "Check Every Cabinet Order Against the Drawing and the Factory
  Acknowledgement" (the review's own suggested wording), the short tagline (sidebar, mobile
  branding, page `<title>`/meta description) is "Cabinet Order Verification", and every page
  description/dialog/email string that said "construction document(s)/project(s)" now says
  "cabinet order(s)" instead (Projects page, project creation dialog, dashboard recent-projects
  card, organization settings, danger-zone delete warning, signup-confirmation email). Left the
  one legitimate placeholder example text ("e.g. Apex Millwork & Construction") alone — that's a
  realistic company name example, not product wording. Live-verified in the browser at both
  mobile and desktop widths — confirmed the new headline and tagline actually render, not just
  compile.
- **Password placeholder dots** — `FIXED` (verified in code): every password field already uses
  the literal `"Password"` placeholder, not pre-filled-looking dots (`login`, `signup`,
  `reset-password` pages).
- **No home/landing page** — `FIXED` (verified live). `frontend/src/app/page.tsx` no longer
  redirects straight to the dashboard/login gate. Signed-in visitors still land on `/dashboard`
  automatically; everyone else gets a one-screen home page: headline, CTAs, and a static
  "see a sample check" section built from the real Chesapeake Bay answer-key data (section 04)
  — the same 3 example discrepancies (construction PLY change, MCV96 quantity change, missing
  F330 filler) a new signup's auto-seeded sample project (P2-1) contains, so the preview matches
  what's actually in-app. Live-verified in the browser: renders correctly at `/`, `Sign In` and
  `Start Free` route to `/login` and `/signup` unchanged.

---

## Known data gap for full three-way testing

The review was only given the designer's drawing and two Marsh acknowledgements — **no dealer
order file**. A true three-way check (Design ↔ Order ↔ Acknowledgement) needs the order the
dealer actually sent to Marsh. **Action needed from the user:** get one real order export for
this same job (from the design software or the dealer's ordering system) so P1-1/P1-2 testing
can cover all three sides, not just Design ↔ Acknowledgement.

---

## Execution order

1. P0-1 (CORS) — unblocks all further live testing. Needs a Render dashboard env var change
   (user action) + a code hardening fallback (my work).
2. P0-2, P0-3 — quick, independent, can be done in parallel with P0-1.
3. P1-3 (upload limit) — quick, unblocks loading the real Marsh catalog for testing.
4. P1-1 + P1-2 — the real correctness work, tested directly against the review's section 04
   answer key once real files can be uploaded.
5. P1-4 — role-based signup.
6. P2 items — after the above are verified working end-to-end.
