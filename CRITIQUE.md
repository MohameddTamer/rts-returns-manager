# Critique — RTS Returns Manager

## Redesign pass, 2026-10-24 (waybill Swiss + English conversion)

This file did not exist before this pass; the redesign is its first entry.

**What changed.** The frontend was rebuilt from the Arabic cream-paper page
into the Printed Waybill direction from DESIGN-RESEARCH.md (section 3.2):
white paper, ink black, one stamp red, returns as numbered forms on a strict
grid, the decision as an animated rubber stamp. Everything user-facing is
English now: the page (LTR), the seeded desk notes in `backend/seed.py`, the
one Arabic API error message and two Arabic code comments in
`backend/app.py` (message text and comments only — no logic moved), plus new
DESIGN.md and SECURITY.md. The README and CHANGELOG were already English;
the CHANGELOG gained a 0.4 entry.

**Evidence.**
- Tests before: `tests/test_api.py` passed (14 assertions, including board
  total 6 and waiting 2 for 2026-10-24) and `tests/test_deepening.py` passed
  50/50. Total 64 checks.
- Tests after: identical. `RTS api tests passed`, `RTS deepening tests
  passed (50 checks)`. Nothing in the suites needed editing — they never
  asserted on page copy or seed note text.
- Numbers unchanged: after reseeding, the database holds exactly 6 seeded
  returns for 2026-10-24 (trackings EG88213–EG88218), 2 of them undecided,
  matching the pre-redesign board the API tests assert.
- The new page serves at `/` with HTTP 200 and the English title; a scan of
  the whole project tree (excluding .db/.log binaries) finds zero lines
  containing Arabic characters.

**Gaps, honestly.**
- The stamp animation and the worn-ink mask were verified in code, not in a
  browser: this environment has no browser to click the flow through, and
  the mask uses `-webkit-mask-image` with a standard `mask-size` fallback,
  so in a browser without mask support the stamp still renders, just
  unworn. The slam animation has a static final state and is disabled under
  `prefers-reduced-motion`.
- Google Fonts is a network dependency at view time; the fallbacks
  (Helvetica/Arial, Consolas) keep the grid honest offline but lose the
  Archivo black weight that carries the masthead.
- The print stylesheet prints the report section only, as before; the
  waybill forms themselves are not part of the printed output yet.
