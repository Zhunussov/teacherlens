# Milestone 4 verification

Local verification date: 2026-10-11. This verifies software behavior with synthetic records, **not academic improvement, psychological diagnosis or real-student outcomes**.

| Check | Observed local result |
|---|---|
| Python unit/integration suite | 72 tests passed; all 56 research tests retained |
| Original problem bank | 24 exact answers and first-step equations verified with SymPy at startup and in tests |
| TypeScript and generated route types | Passed |
| Next.js optimized build | Passed |
| Local development startup | Both services started; session creation and diagnostic readiness passed without uncaught browser errors |
| Chromium end-to-end tests | Four passed, including the complete student journey |
| Automated accessibility | No detected WCAG 2 A/AA and 2.1 AA violations on tested dashboard and diagnostic views |
| Dependency consistency | `pip check` passed |
| JavaScript dependency audit | Zero known vulnerabilities reported by npm at verification time |
| Python compilation | Passed |
| Whitespace check | Passed |

Python 3.11.9, Node.js 24.13.0, Next.js 16.4.0, React 19.3.0, Tailwind 4.3.3, TypeScript 7.0.2 and Playwright 1.64.0. Runtime pins are in `requirements/mvp.txt`; JavaScript transitive versions are in `frontend/package-lock.json`. Browser testing uses Chromium only; no Safari/Firefox coverage is claimed.

## Tested journey

The browser test starts a new synthetic session, records six deliberately incorrect diagnostic answers, reviews feedback, chooses an uncertainty area, discusses stored evidence in guided demo mode, selects a strategy, edits and saves a plan, attempts six assigned problems, completes the different follow-up form, compares counts, writes a reflection, revises the plan, reloads persisted state, then confirms session deletion. Correct synthetic follow-up answers exercise the progress display; their before/after change is not an educational result.

Additional browser checks cover a 390px mobile viewport without horizontal overflow, prerequisites before entering the Studio, rejection of cross-origin/missing-origin session creation, HttpOnly/SameSite cookies, error recovery after a simulated unavailable API, and absence of uncaught browser errors throughout the full journey. Desktop and mobile dashboard screenshots were visually reviewed; screenshots and browser traces remain ignored local artifacts under `outputs/` and `frontend/test-results/`.

Unit/integration checks cover exact rationals, implicit numeric multiplication, unicode signs, hostile/nonlinear/unsupported input, an incorrect supplied step accompanying a correct final answer, unreadable reasoning versus mathematical error, disjoint diagnostic/practice/follow-up IDs, session isolation, expiry, persistence across app restarts, deletion, immutable assessment answers, prerequisites, request limits, successful-change rate limits and provider turn budgets. The partner is tested for explicit demo/fallback labels, student preference, grounded topic references, strict output schema, local-only URLs, remote/cloud rejection, no raw/free-text provider payload, bounded generation, and preservation of prior records after failed writes.

Two concrete browser-discovered integration defects were fixed: canonical browser Origin must be checked against configured frontend origin rather than Next's internal request URL; final follow-up feedback must remain visible before transitioning to reflection. Automated accessibility found and resolved three low-contrast labels. Windows integration tests also caught SQLite connection cleanup, now closed explicitly. Tests cover the resulting behavior.

## CI and integrity

The workflow runs all Python checks plus a separate Node/Chromium job with a production build, full browser journey, accessibility assertions and dependency audit. CI uses only synthetic fixtures and temporary/ignored demo databases; it never opens MAP files or downloads an LLM. Actual remote run status is available in [branch Actions](https://github.com/Zhunussov/teacherlens/actions?query=branch%3Afeature%2Fstudent-strategy-mvp) and is reported after pushing.

The Git publication audit excludes raw data, SQLite files, generated web bundles, dependencies, screenshots, browser traces, credentials and research-derived artifacts. Milestones 1–3 result documents and aggregate metric files remain unchanged. The student application imports no research classifier or MAP loader. Architecture documentation only appends the pivot context.

## Limits of verification

The local Ollama adapter was contract-tested with mocked synthetic HTTP responses; no installed live model or educational dialogue quality was evaluated. The default working interface explicitly uses authored demo guidance. Accessibility automation covers two starting views, not a comprehensive assistive-technology audit. Real identity, consent, encryption, secure erasure and public deployment defenses are absent. Custom checklist edits are student-authored and are not semantically checked as mathematical instructions. Only one small follow-up form is available, without difficulty calibration or a causal learning study.

See [MVP instructions and next milestone](student-mvp.md) and [student architecture](student-architecture.md). The recommendation is educator/student co-design, expanded calibrated problems, accessibility review and privacy/safeguarding work before real student use or learning-gain claims.
