# Actionable feedback — focused public-app improvement

## Base and release boundary

Checked November 13, 2026: PR #1 remained open and unmerged; `origin/main` was `ab66d53`, while `origin/feature/public-student-demo` was `c3e25e9`. The production alias still resolved to Vercel deployment `dpl_9pJMff7FgzJgsLVoMbgiz7RCDYuV` from October 26 (documented application revision `c8253a7`). `feature/actionable-feedback` starts at `c3e25e9`, preserving all later public-demo documentation and unmerged research/product history. This change does not merge, deploy or modify production settings.

## Supported evidence

| Original equation | Entered step | Verified explanation and next practice |
| --- | --- | --- |
| `x + 5 = 12` | `x = 12 + 5` | Removing 5 on the left while adding 5 on the right changes the solution. Show `x + 5 - 5 = 12 - 5`; offer `x + 8 = 13`. |
| `2(x + 3) = 14` | `2x + 3 = 14` | The constant inside parentheses also needs multiplication by 2. Show `2x + 2*3 = 14`; offer `4(x + 2) = 28`. |

`public-demo/lib/feedback.ts` uses narrow authored patterns, then independently checks the entered step and proposed correction with the existing exact rational checker. Whitespace, multiplication-symbol and simple implicit-multiplication variants are normalized. Other wrong steps retain general feedback; matching these patterns does not establish the student's psychological cause, ability or a recurring misconception. No ML model or external AI is called.

An incorrect answer of `17` alone receives no specific explanation. The student can add a step or continue. Adding the step replaces the current diagnostic attempt rather than counting it twice. The optional similar exercise is interactive but transient: it is not added to diagnostic/retest scores or saved as completed planned practice. The approved plan still assigns its normal bank exercises. Seeing an early rehearsal can affect later responses; these are self-practice records, not controlled learning-effect measurements.

The editable plan distinguishes checked answers, supported written-step evidence and the student's own selection. Supported evidence supplies a concrete goal, practice actions and a fresh-problem substitution check; a student's chosen focus still takes priority. Existing plans, local storage format, bank, research reports and the complete learning journey remain compatible. English and Russian copy are authored; independent educational review remains pending.

## Click-through and reproduction

From the repository's `public-demo` directory:

```powershell
npm ci
npm run test:math
npm run typecheck
npm run build
npm run test:e2e
npm run preview
```

Open http://127.0.0.1:3001/ → select English → **Find my starting point** → enter `17` and `x = 12 + 5` → **Check my answer** → expand **Try a similar problem**. Alternatively omit the step, check the answer, then choose **Add one intermediate step** or **Next problem**.

Complete all six questions → **Understand my results** → choose a difficulty or keep **I'm not sure yet** → **Choose a strategy** → review the distinct evidence inputs, practice example and fresh-problem check → edit and approve → **Save and try my plan**. To reproduce distribution feedback, enter `2x + 3 = 14` on the third diagnostic question.

The browser regression runs two separate 390 × 844 sessions with the same `0/2` score in every topic and the same uncertain student selection. Changing only the supported erroneous step changes the leading focus, method, goal, first practice problem and fresh-problem criterion. It also checks rehearsal, plan edits/approval, persistence, overflow and automated accessibility. A separate case verifies answer-only uncertainty, adding a step without duplicating the score and RU/EN switching. Screenshots and browser traces remain in ignored local output directories.

Vercel listed no automatic preview at the initial check. No manual preview or production deployment is part of this task. The public production URL continues to show the prior release until a separately approved deployment.

## Verification — November 13, 2026

- 113 Python research/API/mathematics tests passed.
- 11 public mathematics/session tests passed.
- All five public browser tests passed, including both new cases and the preserved full journey.
- Public-app TypeScript checks and production static build passed.
- Dependency audit reported zero vulnerabilities; Git whitespace check passed.
- New mobile strategy views had no detected automated WCAG A/AA violations or horizontal overflow at 390 × 844. Feedback and both strategy screenshots were visually reviewed. These checks do not certify all devices or accessibility needs.
