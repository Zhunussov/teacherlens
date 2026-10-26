# Admissions review verification — October 26, 2026

**Public demo:** https://teacherlens-public-demo.vercel.app/  
**Review source:** https://github.com/Zhunussov/teacherlens/tree/feature/public-student-demo  
**Application deadline supplied by the project owner:** November 1, 2026.

## Implemented behavior

The deployed static prototype supports diagnostic → verified feedback → student-selected difficulties → editable, explicitly approved plan → targeted practice → different follow-up questions → reflection and revision. It uses 24 originally authored equations and exact rational arithmetic for bounded linear-equation syntax. It distinguishes incorrect answers, non-equivalent steps and unreadable/absent steps. It cannot infer a student's thinking from an answer or diagnose lasting ability.

Public guidance is explicitly rule-based. There is no public live AI conversation, authentication, server-side student database or external inference. Earlier TF-IDF, screening, hierarchical and semantic research and the optional local AI prototype remain preserved with their documented failures and configuration limits. Their tests do not demonstrate live-provider availability or educational effectiveness.

## Checks rerun for this review

| Check | Result |
| --- | --- |
| Python research, API, algebra, provider and bank-parity suite | 113 passed |
| Public math and session suite | 9 passed |
| Browser tests against the actual public HTTPS alias | 3 passed |
| Preserved local MVP browser suite | 6 passed |
| TypeScript checks and production builds | Both applications passed |
| Dependency audits | Both applications: zero reported vulnerabilities |
| Python compile and dependency consistency | Passed |

The live English test completes the full learning cycle, including wrong answers and invalid steps, student choice, plan edits and approval, practice, fresh follow-up, reflection, persistence, revision and reset. The Russian test exercises a 390 × 844 mobile viewport, language switching with method translation, persistence and overflow detection. A third test checks corrupt and blocked browser storage. Tested welcome, strategy, practice and progress views had no detected automated WCAG A/AA violations. This is not an accessibility certification: screen-reader behavior, all keyboard paths, more devices and independent accessibility review remain untested.

The public browser suite reported no application errors or API/LLM/localhost-backend requests. All inputs were synthetic. Mathematical tests cover all 24 original answers and worked steps, fractions, decimal notation, negative signs, unsupported syntax rejection and a correct final answer paired with a wrong intermediate equation. This verifies the implemented subset, not arbitrary school mathematics.

Runtime commit `c8253a7` has a successful hosted CI run: https://github.com/Zhunussov/teacherlens/actions/runs/40332015393. Review-document changes do not redeploy the application. Check the pull request's latest checks before approving a merge.

## Data and branch audit

The repository ignores raw data, CSVs except the hand-authored synthetic fixture, archives, model artifacts, environment secrets, local databases and browser test artifacts. Committed screenshots show only the public welcome screen. The questionnaire requests no identifying details and has no collection endpoint. Hosting services still process ordinary connection metadata; browser-local answer storage is not a promise of anonymous network traffic. No student pilot or feedback is represented as completed.

The owner approved creating the previously absent `main` at foundation commit `ab66d53`. The review branch therefore includes subsequent research and product milestones; its substantial diff reflects preserved history rather than a new redesign. No main merge or repository-setting change is authorized. Restricted competition data and private student responses must remain excluded from every commit and deployment.

## Remaining limits and next action

There is no observed blocker to opening and demonstrating the public learning workflow. Before a student pilot, arrange appropriate consent/assent and educator review of mathematics feedback and Russian/English translations. The small bank is uncalibrated, follow-up forms are not demonstrated to have equal difficulty, answers ship with the static app, and local progress is editable and can be lost. There is no evidence of academic improvement, reliable open-ended misconception diagnosis, Kazakh support or production-scale operation. Vercel Hobby availability remains subject to the account's free resource limits.

For admissions, review the [one-page summary](portfolio-overview.md), [60-second script](demo-walkthrough.md) and [optional anonymous questionnaire](pilot-questionnaire.md). The next milestone should be a modest, consented usability pilot and educator review, followed by documented improvements. Treat usability observations separately from any future controlled evaluation of learning outcomes.
