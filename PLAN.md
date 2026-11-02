# CrossCheckPro — Project Plan

Source of truth for what this product is, what it does, and where it stands.
Synthesized from `CrossCheckPro_MVP_Developer_Spec.pdf` and the system blueprint.
See [TESTING_REVIEW_FIXLIST.md](TESTING_REVIEW_FIXLIST.md) for the active bug list and fix plan.

## 1. What this product is

AI-assisted three-way comparison platform for the cabinet industry: **Design → Order → Manufacturer
Acknowledgement**. Identifies discrepancies between what was designed, what was ordered, and what the
manufacturer confirmed — before fabrication begins.

Domain: crosscheckpro.ai

## 2. MVP scope (locked)

**In scope:** file upload, AI data extraction, normalization, three-way matching engine, discrepancy
detection, severity classification, human review workflow, exportable reports.

**Out of scope for MVP:** full design/geometry validation, multi-manufacturer support, automated
corrections, ERP integrations, learning/feedback-trained AI.

**Locked inputs:** one manufacturer, one order export format, one acknowledgement format (currently:
Marsh Furniture).

## 3. Core workflow

1. Create job
2. Upload files (Design PDF, Order PDF, Acknowledgement PDF)
3. Extract structured data (AI: OCR + vision)
4. Normalize line items (SKU → canonical form, e.g. `B36` → Base Cabinet 36")
5. Compare datasets (three-way matching engine)
6. Generate discrepancy report (severity-classified)
7. Human review
8. Export results

## 4. Matching engine logic

**Match priority (in order):**
1. Exact normalized SKU match
2. SKU + size match
3. Category + size match
4. Fuzzy description match

**Match status types:** matched, missing, extra, changed, uncertain

**Severity classification:**
- **Critical** — missing items, rejected items, SKU mismatches
- **Warning** — quantity, size, finish, or door style changes
- **Info** — minor differences, informational notes

## 5. Data model (canonical)

- **Project** — project_id, customer_name, manufacturer, status
- **Order Line Item** — sku, normalized_sku, description, quantity, dimensions, finish, door_style
- **Acknowledgement Line Item** — same + acknowledgement status
- **Match Result** — match_status, differences, severity, confidence_score, review_status

## 6. Current architecture (as built)

- **Frontend:** Next.js (`frontend/`), deployed as `crosscheck-pro-ai-tool.onrender.com`
- **Backend:** FastAPI (`backend/`), deployed as `crosscheck-pro-ai.onrender.com`
- **Database:** Supabase Postgres, RLS enabled on all public tables
- **Auth:** dual path — Supabase Auth (client-side, primary when configured) with FastAPI-backend
  fallback; backend auto-provisions local user/org records on first authenticated request (JIT
  provisioning in `app/api/dependencies.py`)
- **AI extraction:** OpenAI (configurable via `AI_PROVIDER`), with manufacturer-aware Cabinet Code
  Intelligence hierarchy (manufacturer dictionary → spec-book → generic classifier → uncertain)
- **File storage:** Supabase Storage
- **Background jobs:** Celery (processing, spec-book extraction)
- **Email:** SMTP (Gmail relay) for verification/reset — superseded by Supabase's own auth email
  for the primary (Supabase-first) signup/reset path

## 7. Performance targets

- < 30 seconds per job
- ~10MB file size support (**known gap** — real manufacturer spec guides run 14MB+/576 pages;
  see fix list P1-3)

## 8. Success criteria

- 90%+ SKU extraction accuracy
- 90%+ match classification accuracy
- Accurate discrepancy detection against real test data (see fix list section 04 "answer key"
  for the concrete real-data benchmark this must pass)

## 9. Status

MVP feature set (upload → extract → normalize → match → review → report) is built. A live QA pass
against the deployed Render instance (2026-11-01) found the production site's auth is fully blocked
by a CORS misconfiguration, meaning **none of the core cabinet-checking features have been verified
against real production traffic yet**. See the fix list for the full breakdown and priority order.

## 10. Future phases (post-MVP, not in current scope)

Manufacturer rules engines, full design/geometry validation, multi-manufacturer support, ERP
integrations, learning from corrections.
