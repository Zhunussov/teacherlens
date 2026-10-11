# Student strategy MVP — Milestone 4

TeacherLens now explores a student-first learning strategy partner: **“Every student is different. Every student deserves a different strategy.”** The aim is to help students notice difficulties, choose a method, practice deliberately and reflect. It is not a diagnostic authority or an answer-generating chatbot.

The Milestones 1–3 research, results, scripts and classifiers are preserved. Their failure on unseen labels motivates this pivot. The student application imports none of those classifiers and uses none of the restricted MAP data, derived models or response examples. No academic improvement or multilingual capability is claimed.

## What works

1. A local synthetic learner session with isolated, persistent records, expiration and deletion.
2. A six-problem diagnostic from an original 24-problem bank: linear equations, distribution, and negative-number operations in equations.
3. Exact mathematical feedback, with separate final-answer and optional intermediate-equation checks. An incorrect answer is not a verified explanation of a student's thinking. Even a correct answer can accompany a non-equivalent entered step.
4. An evidence-grounded Strategy Studio: stored diagnostic counts, student-selected uncertainty, clarification questions, multiple practice strategies and explicit tradeoffs.
5. Student-editable goals, checklist, minutes/session and intended session count. Assigned practice follows checked difficulties plus the chosen strategy.
6. Practice attempts and feedback, a distinct six-problem follow-up form, before/after counts and written reflection. Students can revise their plan without losing history.
7. Five responsive views, keyboard-accessible controls, visible errors, resumable assessments and confirmation before deleting a session.

### What is demo or limited

The default **guided demo is authored rule-based guidance, not a live AI conversation**. The contextual Studio extension is documented in [context-aware conversation](context-aware-studio.md). Diagnostic checks, stored evidence, plan editing, practice and progress are functional. Nothing uses simulated scores. Synthetic browser tests deliberately produce before/after scores to exercise the software; these are not measured learning outcomes.

An optional local Ollama model now generates contextual conversational prose and a structured strategy proposal using the current message, up to four recent turns, relevant checked mathematics, student-confirmed difficulty choices and a bounded current-plan summary. Deterministic checking remains separate. No full session, student name or hidden solution key is sent. Obvious contact patterns are masked, but arbitrary prose is not guaranteed anonymous. Synthetic testing only; do not enter private student records.

The model cannot grade, modify the bank, call tools or save a plan. Output schema, lengths, locale, strategy catalogue, schedule and question count are validated. Numerical equations and selected unsupported diagnostic claims in generated prose are rejected. These checks are not a semantic proof that all prose is correct. Suggestions are labeled for student review, with verified facts rendered separately. A student edits and explicitly approves the goal, uncertainty, rationale, checklist, schedule, success criteria and checkpoint before saving.

No local model is installed automatically, and the live provider has not been educationally validated. Its HTTP contract is tested with synthetic mocked responses; an unavailable or invalid model response explicitly falls back to demo guidance. Hosted providers, paid APIs and credential entry are absent. The provider boundary can support future reviewed adapters, but no remote provider is enabled.

This is a **local synthetic demo**, not a school deployment. Do not enter private student records. There are no real accounts, parental consent workflow, school tenancy, account recovery, encrypted storage or production authentication. A seven-day opaque session capability isolates browser sessions; it is not a verified student identity. The interface labels the limitation throughout.

## Development

Validated runtime: Python 3.11.9 and Node.js 24.13.0. Install from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements/mvp.txt -e ".[mvp]"
cd frontend
npm ci
cd ..
python scripts/dev_mvp.py
```

On Linux/macOS activate with `source .venv/bin/activate`. Open **http://127.0.0.1:3000**. The launcher binds both services to loopback, generates a shared ephemeral server-only gateway key, disables Next telemetry, and stops both when interrupted. The API runs on port 8000. No Kaggle files are required or opened.

Session data resides in ignored `data/student-mvp/demo.sqlite`. The browser keeps an HttpOnly, SameSite=Strict seven-day cookie; no session credential is placed in localStorage or a response body returned to browser code. “Delete & restart demo” deletes the current session records. Expired sessions are removed when a new one starts. SQLite WAL/deleted pages and local backups may retain forensic remnants; deletion is not a certified secure erase.

For a local optimized build:

```powershell
cd frontend
npm run build
cd ..
python scripts/dev_mvp.py --production-build
```

This serves locally; it does not deploy. Keep ports 3000 and 8000 free. Restarting the launcher rotates its internal key, while valid saved browser sessions remain usable. If a session expires, the UI starts a new synthetic session.

### Optional local model

Install Ollama separately and explicitly obtain a suitable **local, non-cloud** model after reviewing its licence and resource requirements. Nothing is downloaded by TeacherLens. Then configure before starting the launcher:

```powershell
$env:TEACHERLENS_PROVIDER = 'ollama'
$env:TEACHERLENS_OLLAMA_MODEL = 'your-installed-local-model'
$env:TEACHERLENS_OLLAMA_URL = 'http://127.0.0.1:11434'
python scripts/dev_mvp.py
```

The configured provider label does not assert that inference succeeded. Every actual turn records `demo` or `ollama`, including fallback notices. Local-only URL checks reject remote hosts, embedded credentials and cloud-named models. A trusted local service remains the operator's responsibility. Defaults are demo; absence of a model never masquerades as live AI.

Generation is bounded to 900 output tokens, an 8,192-token context, a 12-second HTTP timeout, a 32 KB response and eight strategy turns per session (including demo/fallback turns). Student text is capped at 600 characters, request bodies at 4 KB, plans at five short steps, and sessions at 40 successful changes/minute. No automatic retry or model download spends resources. The client displays errors and preserves previously committed work.

## Curriculum and verification

All 24 questions are original authored expressions in `student/math_engine.py`. Each exact rational solution and example first step is verified against the equation with SymPy, both in tests and at API startup. Manual arithmetic review accompanies this computational verification; qualified educator review of wording and scaffolding remains a Milestone 5 requirement.

Within each of the three topics:

| Positions | Purpose |
|---|---|
| 1–2 | Starting diagnostic |
| 3–4 | Assigned practice |
| 5–6 | Follow-up assessment |
| 7–8 | Additional verified bank material reserved for future sequencing |

The diagnostic and follow-up share skill structure, with different numerical values and no overlapping problem IDs. They are not empirically equated assessment forms. Feedback is shown after each submission, including worked steps on request, so this is a learning activity with feedback rather than a blind high-stakes test. Each assessment answer is immutable; unfinished assessments resume. One diagnostic and one follow-up are available per session; fresh forms are needed before repeated outcome evaluation. Attempting an assigned exercise permits progression regardless of correctness, which keeps students from being trapped but does not indicate mastery.

The parser accepts a bounded arithmetic AST: numbers, x, +, −, *, / and parentheses; decimal and fraction values are exact rationals. It supports ordinary numeric implicit multiplication such as `2x` and `2(x+3)`. Powers, functions, symbolic denominators, nonlinear expressions, huge constants and deeply nested inputs are rejected. No Python evaluation or SymPy string evaluation is applied to user input. See [SymPy's parsing warning](https://docs.sympy.org/latest/modules/parsing.html).

“Verified error” means a submitted value fails the original equation or an entered single-step equation does not preserve its unique solution. “Possible explanation” remains conditional. “Insufficient evidence” covers absent/unreadable reasoning; unreadable notation is not labeled a math mistake. Equivalent equations show only that entered transformation, not the whole reasoning process. Strategy evidence includes non-equivalent steps even when the final answer is correct.

## Testing

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
python -m pip check
cd frontend
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
npm audit --audit-level=high
```

Browser tests start and stop both local servers using an isolated ignored `outputs/mvp-browser-tests.sqlite`; production build first. CI installs Chromium's required system libraries on Linux. Python tests use temporary databases and synthetic records. Research tests remain enabled. See [verification results](student-mvp-verification.md) for the actual run status.

## Milestone 5 recommendation

Conduct educator and student co-design with consent and appropriate safeguarding. Verify question wording, scaffolding, accessibility, cognitive load and whether students understand evidence versus hypotheses. Expand and calibrate parallel forms before evaluating progress, include fraction solutions and more varied examples, and make revisions drive new practice cycles. Test strategy usefulness, false reassurance and review burden against a transparent non-AI comparison. Freeze an outcome protocol before measuring learning gains.

Before using real student records, implement an appropriate identity/consent/retention model, encryption and access controls, threat-model any deployment and review providers' terms and data handling. Keep mathematical grading deterministic. Add an evaluated, evidence-limited model only where it improves collaboration. Native Kazakh/Russian curriculum, localization and expert-annotated tests are separate work; current English content makes no multilingual support claim.
