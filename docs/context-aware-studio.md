# Context-aware Strategy Studio

The previous Studio never sent the student's message to its selector. It chose catalogue entries from topic counts and a difficulty dropdown, then rendered the same score paragraph. The active workflow now uses bounded contextual dialogue, with a separate deterministic mathematical checker. Research results and the original diagnostic/practice/follow-up flow are preserved.

## Functional behavior and provenance

| Component | Current behavior |
|---|---|
| Mathematics | Bounded arithmetic parser and SymPy compare unique solutions of a reference equation and an entered step. Original supported bank and grading remain unchanged. |
| Local AI | An explicitly configured local Ollama model can generate conversational prose and a validated structured strategy proposal. This is implemented and HTTP-contract tested; no live model was available during verification. |
| Default demo | Authored rules respond to recognized equations, corrected steps, sign/expansion mentions and requests for alternatives. Every turn is labeled demo; these rules do not understand arbitrary natural language. |
| Plans | A proposal remains unsaved. Students review/edit fields and explicitly approve saving; the server requires a strict boolean approval. Later edits require renewed approval in the interface. |
| Localization | Schemas accept `en`, `ru`, `kk`. Configured local models may return these locales. English-only demo fallback is explicit. UI, bank, verified feedback and authored question scaffolds remain English. |

For the synthetic message “Equation was x+5=12, so I moved +5 to the right and got x=17, but it was wrong,” the checker establishes that `x=17` does not preserve the original solution. It explains undoing addition by subtracting on both sides and asks for the next equation, without disclosing the unattempted final solution. “Moving a term” hiding an operation and an arithmetic slip are possible explanations, not verified causes. A subsequent `x+5-5=12-5` is checked against the retained reference and receives different feedback. Students can disagree and choose an alternative.

The Studio accepts an optional recorded/assigned problem and an explicit step. Recognizable arithmetic spans in prose can establish a reference; a subsequent step uses the recent reference. An explicitly new equation switches it. Extraction is intentionally limited, not a general math-language parser: unsupported notation needs clarification, and a reference inferred from recent conversation may need student correction. Equivalence verifies the entered equation's unique solution, not a complete derivation, the student's intent, or all unseen intermediate operations. Identity/contradictory/nonlinear equations are outside this curriculum.

## Context boundaries

`student/dialogue.py` assembles:

- Current message, bounded to 600 characters, and at most four recent student/partner exchanges.
- Current original equation, candidate step, deterministic verdict, checked hint and next-step question. No hidden solution key is included.
- One relevant recorded attempt, when identifiable, and the three topic-level diagnostic aggregates.
- Recent explicitly selected difficulty choices, identified as student reflections rather than causes.
- The current plan's method, goal, checklist and intended schedule; no full plan revision history or reflections collection.

No session capability, student name, limiter state, full diagnostic response collection or MAP record reaches the provider. Obvious email/telephone patterns are masked. This is minimization, not guaranteed anonymization: arbitrary prose may still contain names or personal information. All usage remains local and synthetic; no hosted adapter is provided. The configured trusted local service receives context via loopback HTTP, and real-student use needs a reviewed consent/data policy.

## Provider and output validation

The existing `OllamaProvider` now shares its HTTP transport between the retained legacy selector and active `respond(context)` method. It allows only local HTTP endpoints, rejects embedded credentials and cloud-named models, disables environment proxy use, bounds responses to 32 KB, has a 12-second HTTP timeout, requests at most 900 generated tokens with an 8,192-token context, and makes no automatic retries. Eight conversation turns per session include demo/fallback turns. The 4 KB browser request and existing mutation limits remain in force. The timeout is an HTTP I/O timeout, not a guarantee of model latency or a total compute budget.

The model receives a JSON context as untrusted data under a system instruction; no tools or file execution are available. Strict Pydantic schemas reject unknown fields, duplicate/unsupported strategy IDs, inconsistent locale, oversize text, invalid schedules and multiple prose questions. Generated prose may not contain numeric digits or equality/comparison formulas, and selected diagnostic/answer-revealing phrases are rejected. The server separately renders verified math and, when working through a checked equation, chooses the focused next-step question. This limits unverified arithmetic and solution dumping, but text filters do not prove pedagogy, language quality or semantic safety. Generated suggestions are explicitly distinguished from verified facts and remain reviewable.

Timeout, malformed JSON, validation failure or unsupported locale produces an authored English demo turn with a sanitized explanation. Missing local-model configuration also exposes a clear demo notice. No provider credentials are required for local Ollama; the internal gateway key remains server-only and is generated by the launcher. No secret or provider error body is shown to the browser.

## Structured plan contract

The proposal contains locale, method ID, goal, current uncertainty, rationale, one to five practice steps, five to twenty-five minutes per session, one to five intended sessions, observable success criteria and a follow-up/reflection checkpoint. Supporting evidence is added by the server from stored diagnostic counts and checked conversation mathematics, never accepted as model-authored truth.

Each proposal references its owning conversation turn. Saving an older proposal keeps that turn's evidence even after newer conversation; cross-session or nonexistent proposal references are rejected. Evidence for a student-selected alternate method is recomputed from the corresponding diagnostic topic. Plans are persisted only after explicit approval, and preserve existing practice and assessment histories. Arbitrary student checklist edits and success criteria are not semantically validated or automatically scored. Small-sample topic counts are not long-term ability estimates; follow-up forms remain uncalibrated.

## Configuration and reproduction

Follow the [MVP setup](student-mvp.md) to install the locked Python/JavaScript dependencies. Default:

```powershell
python scripts/dev_mvp.py
```

For an already installed and independently reviewed local model, start Ollama separately and configure the backend process before running the launcher:

```powershell
$env:TEACHERLENS_PROVIDER='ollama'
$env:TEACHERLENS_OLLAMA_MODEL='<your-installed-local-model>'
$env:TEACHERLENS_OLLAMA_URL='http://127.0.0.1:11434'
$env:TEACHERLENS_OLLAMA_LOCALES='en'
python scripts/dev_mvp.py
```

Enable `en,ru,kk` only if the chosen model has been checked for those response languages. A matching locale code in JSON is not proof of correct language or reviewed mathematics. No model download, paid service, live multilingual capability or educational validation is implied by these instructions.

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
python -m pip check
cd frontend
npm run typecheck
npm run build
npm run test:e2e
npm audit --audit-level=high
```

Stop the local development launcher before browser tests, which start isolated test services on the same ports. Browser tests use only synthetic records and ignored databases/screenshots. Live providers are mocked in unit/integration tests; the default end-to-end journey uses demo rules.

## Verification and next work

Verification date: 2026-10-11. The original 56 research tests remain enabled. Conversation tests cover message relevance, wrong/equivalent transformations, unreadable steps, multi-turn correction, explicit new problems, disagreement, bounded context, current plan/history, minimization, strict structured output, locale fallback, provider timeout, missing configuration, proposal provenance and editable approval. Browser tests cover the whole preserved journey plus contextual conversation and unsaved proposal review.

| Check | Observed local result |
|---|---|
| Python unit/integration suite | 90 passed: 56 research, 16 preserved MVP and 18 contextual dialogue tests |
| TypeScript / generated route types | Passed |
| Production build | Passed |
| Chromium end-to-end suite | Five passed; preserved journey plus contextual Studio/approval |
| Automated accessibility | Zero detected A/AA violations in tested dashboard, diagnostic, Studio and plan-review views |
| Dependency consistency / JavaScript audit | `pip check` passed; npm reported zero known vulnerabilities |
| Python compilation / whitespace | Passed |

Remote CI status is reported after pushing. A read-only check found no available local Ollama service; live generation and actual Russian/Kazakh output quality were not exercised. No real student record, raw competition data, model download or academic outcome experiment was used. The generated reply and authored mathematical next-step question have distinct provenance labels; a model-configured turn does not relabel authored scaffolding as generated prose.

Next: evaluate a fixed local model with educator-reviewed dialogues (including injection attempts, repeated arithmetic slips, disagreement and language switching), assess unwanted answer disclosure and false reassurance, and review translated curriculum separately. Establish a real-student privacy/consent policy before handling personal records. Do not infer educational gains from the synthetic tests.
