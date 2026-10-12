# Optional Hugging Face strategy partner

Implemented on `feature/huggingface-ai-integration`, based on context-aware Studio commit `1d773da`. Research results and the original diagnostic/practice/retest workflow are preserved. No model weights or new runtime dependencies are required. Ollama remains an optional legacy provider; it is not required for cloud AI.

## Verified route and free-credit restrictions

Public metadata checked on 2026-10-12 (no token and no inference request):

- Model: [`Qwen/Qwen3-4B-Instruct-2507`](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
- [Model provider mapping](https://huggingface.co/api/models/Qwen/Qwen3-4B-Instruct-2507?expand=inferenceProviderMapping) reported Nscale and Featherless AI live for conversational inference. TeacherLens pins Nscale, without automatic routing or provider switching.
- [Router model metadata](https://router.huggingface.co/v1/models) reported Nscale structured-output support, `is_free=false`, input $0.01 and output $0.03 per million tokens. The [official model/provider comparison](https://huggingface.co/inference/models?model=Qwen/Qwen3-4B-Instruct-2507) listed the same prices. Availability/pricing can change.
- TeacherLens uses the documented [OpenAI-compatible chat-completion endpoint](https://huggingface.co/docs/inference-providers/tasks/chat-completion): `https://router.huggingface.co/v1/chat/completions`, model `Qwen/Qwen3-4B-Instruct-2507:nscale`, a Hugging Face bearer token and [JSON schema output](https://huggingface.co/docs/inference-providers/guides/structured-output).

This model is metered, not intrinsically free. [Hugging Face pricing](https://huggingface.co/docs/inference-providers/pricing) currently gives free users $0.10 monthly inference credits, subject to change. HF-routed requests consume those credits; custom provider keys do not qualify. Credits can be replenished by purchasing credits, and an account's configured custom provider key can be substituted transparently by HF. TeacherLens does not buy credits, activate billing, use subscriptions or call any payment API. No authorized account/token was available to verify account-specific eligibility or remaining credits.

**Free-only setup prerequisite:** use a free account without purchased credits, paid subscriptions, billing arrangements or custom provider keys. Check the HF account's Inference Providers settings before enabling the adapter. `HF_FREE_TIER_CONFIRMED=true` is your explicit confirmation of that check; the app cannot independently verify account billing/credit state. Request caps are not a monetary guarantee on a paid or otherwise funded account. Other applications may share the same credits. If you cannot establish these conditions, leave `AI_PROVIDER=demo` and do not enable cloud requests.

## Windows PowerShell setup

From the repository root, with the existing dependencies installed:

```powershell
Set-Location C:/Users/svato/source/teacherlens
Copy-Item .env.example .env
notepad .env
```

Leave `HF_TOKEN=` empty in this file. After checking the free-only account conditions above, set these non-secret values:

```dotenv
AI_PROVIDER=huggingface
HF_MODEL=Qwen/Qwen3-4B-Instruct-2507
HF_FREE_TIER_CONFIRMED=true
HF_DAILY_REQUEST_LIMIT=5
HF_MONTHLY_REQUEST_LIMIT=50
```

Create a fine-grained token in [HF token settings](https://huggingface.co/settings/tokens) with **Make calls to Inference Providers** permission. Enter it into the launching PowerShell session without putting the value in shell history or repository files:

```powershell
$teacherLensSecureToken = Read-Host 'Hugging Face token' -AsSecureString
$teacherLensTokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($teacherLensSecureToken)
try {
    $env:HF_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($teacherLensTokenPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($teacherLensTokenPointer)
    Remove-Variable teacherLensSecureToken, teacherLensTokenPointer
}
.venv/Scripts/python.exe scripts/dev_mvp.py
# After stopping the app, clear the session token:
Remove-Item Env:HF_TOKEN
```

Open `http://127.0.0.1:3000/`, complete the fictional diagnostic and enter Strategy Studio. Open **AI configuration and application limits**, then **Check AI configuration**. This reads local readiness and application counters; it makes no inference call, checks no account balance and does not prove connectivity. Missing token, missing free-account confirmation or an unsupported model produces an explicit demo notice. The launcher reads only allowlisted literal `.env` settings; existing process variables take precedence. It never evaluates shell expressions and removes `HF_TOKEN` from the Next.js child environment.

For a manually authorized small live test, use fictional content such as: “Equation was x+5=12, then x=17 because I moved the term.” Confirm that the message, retained conversation and plan contain **fictional data only**, then submit once. The checkbox resets after every successful turn. A successful response is labeled **Hugging Face-generated conversation**; failure is labeled **Guided demo response** with its reason. Inspect the local last-result counter. Do not submit private minors' records. Stop after a small number of calls and inspect HF usage before continuing. No live test was performed during implementation.

## Context, mathematics and plans

The provider receives the current message (up to 600 characters), at most two recent turns (student 300 / partner 350 / question 120 characters each), one relevant recorded attempt, server-verified equation evidence, topic counts, explicitly selected difficulties, a short current-plan summary and the authored method catalogue. The JSON context is capped at 12 KB UTF-8. Full session records, student identity, capability tokens, reflection history and hidden answer keys are not sent. Obvious contacts are masked; this is minimization, not reliable anonymization. The whole retained context must be fictional, not just the newest message.

System instructions treat that JSON as untrusted data. The model should address the message, allow disagreement, guide one change at a time and ask at most one question. Its strict structured output contains a learning goal, uncertainty, rationale, practice steps, bounded schedule, success criteria and checkpoint. Server-owned evidence is attached after generation, never accepted as model-authored fact. The student edits and explicitly approves a proposal before saving; no strategy is saved automatically.

The existing safe grammar and exact arithmetic still verify supported linear equation transformations. For example, `x=17` is non-equivalent to `x+5=12`; the separate server hint asks the student to subtract on both sides. This does not establish the student's underlying cause or long-term ability. Generated prose cannot supply numerical equations; server mathematical scaffolding has distinct provenance. Mathematical checks do not validate every pedagogical claim. Unsupported notation yields insufficient/unreadable evidence rather than an invented diagnosis.

The cloud contract requests `en`, `ru` or `kk`. Mocked tests validate all three schema/response paths. Actual multilingual quality has not been assessed; the UI, authored curriculum, method options and deterministic mathematical feedback remain English. Generated translations and psychological claims require educator review. Existing lexical checks are limited and do not guarantee truth, safety or resistance to prompt injection in any language.

## Limits, failures and privacy

- Output: 700 tokens, temperature 0.2, one non-streaming request, no tools/retries/provider switching; 12-second HTTP operation timeout and 32 KB response cap. Timeout applies to network operations, not an independently guaranteed total wall-clock deadline.
- Default application-wide budget: five attempted requests per UTC day and fifty per UTC month. Configurable bounds: daily 0–10, monthly 0–100. Failed attempts count. Separate SQLite counters are atomic and persist across restarts/session deletion at `<TEACHERLENS_DB>.cloud-budget.sqlite`. Use one shared database path for all app instances; resetting/moving its budget file defeats the local guard. UTC clock correctness is assumed.
- HTTP 429 pauses requests for five minutes; 401/403 also pause while configuration is corrected. HTTP 402 blocks for the current UTC month. These are application policies, not claims about HF reset dates. Remaining application counts are not remaining HF credits. Invalid/truncated schema, unsupported locale, oversized output, timeout and other errors use clearly labeled authored English demo rules. Provider error bodies and credentials are never returned or logged by this adapter.
- The session's existing eight-turn limit and gateway protections remain. `/provider/health` requires the server gateway and session capability. Health checks never call HF. `.env`, raw competition data, databases, logs, reports containing records, screenshots and generated artifacts remain ignored; only the empty-token `.env.example` is allowlisted.
- [HF security documentation](https://huggingface.co/docs/inference-providers/security) describes routed-request handling, but the selected provider's policies also apply. This milestone does not establish permission to transmit real student records, nor guarantee external retention behavior. Local synthetic records remain in the existing database.

## Verification

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m compileall -q src tests scripts
.venv/Scripts/python.exe -m pip check
git diff --check
Set-Location frontend
npm run typecheck
npm run build
npm run test:e2e
npm audit --audit-level=high
```

Stop the development launcher before browser tests. The browser-test launcher forces `AI_PROVIDER=demo` and removes the token even if the operator configured cloud AI. Provider tests use HTTP mock transports and fictional fixtures. Browser cloud metadata/output is explicitly mocked; deterministic checks still execute locally. The full research, diagnostic, conversation, plan, practice, retest and reflection tests remain enabled.

Observed local verification, 2026-10-12:

| Check | Result |
|---|---|
| Python unit/integration tests | 109 passed: 90 preserved tests and 19 cloud/configuration tests |
| Chromium end-to-end journeys | Six passed, including mocked cloud consent and the complete learning workflow |
| TypeScript / production build | Passed |
| Automated accessibility | Zero detected A/AA violations in tested views, including cloud Studio consent |
| Python compilation / dependency consistency | Passed |
| npm dependency audit | Zero known vulnerabilities |
| Whitespace / publication policy | Passed; no restricted data or secrets staged |
| Genuine live inference / language quality | Not tested: no token configured, no credits consumed |

Remote CI status is reported with the pushed commit. Public metadata availability is not a successful inference test, and mocked responses are not model-quality measurements.

Next: one explicitly approved live fictional dialogue in each locale, then educator review of relevance, incorrect reassurance, answer disclosure, disagreement, unsupported notation and adversarial prompts. No academic benefit, production readiness or reviewed multilingual curriculum is claimed.
