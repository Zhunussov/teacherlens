# Public student demo

## Architecture and boundaries

`public-demo/` is an independent Next.js/TypeScript application. `next build` exports only HTML, JavaScript, CSS and an original SVG icon to `out/`. There are no API routes, server functions, authentication, database, telemetry SDKs, external fonts, model downloads or LLM calls. Russian is the initial locale; English is selectable. After the initial asset load, the learning journey makes no application network requests. A fresh page load still requires the site assets; this is not an installed offline app.

The older `frontend/` + FastAPI + SQLite prototype remains available separately. All Python research and historical findings are preserved. The experimental HF adapter is not imported into, configured in or deployed with the public application. A Vercel deployment must set its **Root Directory to `public-demo`**, not the repository root or `frontend`.

The public engine uses the exact original 24 problems, exported as `lib/bank.json`. A Python regression test compares every field against the original bank and verifies every answer and worked equation. The TypeScript parser uses bounded tokens and exact reduced BigInt rationals, never `eval`, user-controlled JavaScript or floating-point equality. It supports numbers, decimals, fractions, x, unary signs, parentheses, addition, subtraction, multiplication by constants and division by nonzero constants. It rejects nonlinear products, powers, functions, multiple variables, ambiguous equations, zero division, inputs over the limits and equations without a unique solution. This is a deliberately bounded linear subset, not a complete replacement for SymPy. Decimal commas are additionally accepted for Russian users.

An intermediate equation is equivalent when it preserves the unique solution; this does not prove every operation or reveal the student's reasoning. Unreadable steps are distinguished from verified non-equivalence. Correct final answers paired with bad steps still inform strategy selection.

## Learning experience

Welcome → six diagnostic problems → evidence and student-selected difficulty → editable strategy → targeted practice → six different follow-up problems → comparison, reflection and revision.

The original bank uses positions 1–2 per topic for the diagnostic, 3–4 for practice, 5–6 for the follow-up and reserves 7–8. These sets are disjoint. Question difficulty has not been empirically calibrated.

The rule engine ranks difficulty evidence using incorrect answers and verified bad steps. An explicitly selected difficulty is prioritized; up to two topics keep practice manageable. Four transparent methods include balancing both sides, expanding every term, making signs visible and substitution checking. Each has a rationale and tradeoff. A plan contains a focus, goal, actionable checklist, intended schedule, success criteria and fresh-check checkpoint; saving requires explicit approval. Plans remain editable. Minutes and sessions are intentions, not measured attendance. An attempt counts as practice even if incorrect; retries are available. A session has one follow-up form. Revising a plan preserves historical assessment results rather than representing a repeated form as fresh evidence.

## Localization and data

RU/EN cover navigation, instructions, notation help, feedback, explanations, authored methods, schedules, success criteria, privacy notices and reflection prompts. User-written plan/reflection text remains in its original language. Independently reviewed educational translation and Kazakh are deferred; no tested Kazakh or multilingual model capability is claimed.

Progress is held in versioned browser-local storage under `teacherlens-public-v1`. Restoration validates structure, problem assignments, answer syntax and plan bounds, recomputing mathematical verdicts. Corrupt storage restarts transparently; blocked storage permits an in-memory session with a warning. Reset replaces stored answers, plans and reflections. This is not encrypted storage or a proctored assessment; users can edit their browser data and inspect bundled solutions. There is no cross-device recovery or account system. No names, emails or schools are requested. The hosting service may retain standard request metadata; the application sends it no answers or reflections. Use appropriate school/guardian arrangements for any pilot with minors, and keep personal records out of free-text fields.

## Reproduction and deployment

```powershell
Set-Location C:/Users/svato/source/teacherlens/public-demo
npm ci
npm run test:math
npm run typecheck
npm run build
npm run test:e2e
npm run preview
```

Static preview: `http://127.0.0.1:3001`. The preview command and browser tests use port 3001, leaving the research prototype separate. Node.js 24 is used in CI. Modern browsers with BigInt support are required. The locked Next.js and React releases include the October 2026 security patches; the older prototype receives the same dependency patches without rewriting its logic.

Vercel Hobby Git-import settings: Root Directory `public-demo`; Framework Next.js; Install `npm ci`; Build `npm run build`; Output: leave the Next.js preset default (`.next`); **no environment variables, integrations, database or paid add-ons**. `vercel.json` uses the Next.js adapter build directory `.next` and restrictive headers. Next.js detects `output: export` and publishes the static `out/` assets; do not override the adapter directory to `out` or it will look for its manifest in the wrong folder. For CLI uploads, run from `public-demo/`, which is then the uploaded project root (`./`). `.vercelignore` excludes local secrets, dependencies, tests and generated artifacts from CLI uploads. Restricted data is outside this directory and never tracked. If importing through Git, select the `feature/public-student-demo` branch. No main merge is necessary. The account's existing free resource limits may block publication independently of application correctness; never solve that by upgrading without authorization.

Public verification can run against a real deployment:

```powershell
$env:PUBLIC_DEMO_URL = 'https://teacherlens-public-demo.vercel.app'
npm run test:e2e
Remove-Item Env:PUBLIC_DEMO_URL
```

The URL above is the verified production alias. It returned HTTP 200 without authentication and passed the full public browser suite on October 26, 2026.

## Launch verification

The Node suite verifies exact arithmetic, all bank answers/steps, invalid and hostile input, step/answer distinctions, student-driven targeting, state validation, plan revision and locale key coverage. Python checks the original-bank parity alongside all existing research tests. Browser tests cover the entire English journey, a Russian mobile journey, RU/EN method translation, invalid answers, persisted progress, revised plans, reset, blocked/corrupt storage and automated accessibility. They record API/LLM/backend request absence. The same suite can exercise the public HTTPS deployment. No measured academic benefit, adoption or live AI result follows from these tests.

Local results on 2026-10-26: 113 Python tests, nine public math/session tests, three public browser journeys and all six preserved prototype browser journeys passed. Both app directories passed TypeScript validation, production builds and dependency audits with zero known vulnerabilities. The public static preview applies the same security headers as the Vercel configuration; tested accessibility views reported no detected WCAG A/AA violations. These results do not establish a public deployment until the HTTPS journey is separately verified.

## Verified public launch — October 26, 2026

Production: https://teacherlens-public-demo.vercel.app. Application source/configuration: commit `c8253a7`, deployed to the existing Hobby team using the official Vercel CLI from `public-demo/`. The CLI uploaded that folder as project root; no Python, local databases, credentials or restricted artifacts were included. Production build succeeded after correcting the Next.js adapter manifest directory to `.next`. The generated deployment has a production alias accessible anonymously, even though generated deployment/preview URLs may have Vercel protection.

All three browser journeys passed against the public alias: complete English cycle, Russian mobile/localization journey and storage-error handling. There were no API, HF, Ollama or localhost-backend requests. Security headers were observed on the anonymous HTTPS response. No subscriptions, upgrades or paid integrations were activated. The existing account displayed free-resource usage warnings; continued availability remains subject to Vercel Hobby limits.

No manual Vercel action remains for this launch. Automatic Git deployment is intentionally not connected: the repository's default branch is the older research foundation, and no merge or repository setting was changed. For updates, deploy from `public-demo/` with `vercel deploy --prod --yes --project teacherlens-public-demo --scope temirlan-s-projects1`, then rerun the public browser suite. If Git automation is configured later, explicitly select the public feature branch and root directory rather than the foundation branch. Share the public feature-branch source link in the application portfolio.
