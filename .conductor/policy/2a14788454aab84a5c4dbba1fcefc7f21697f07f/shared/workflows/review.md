# Independent review workflow

Work in a separate review session against a specified immutable head SHA and base SHA. Read the task contract and relevant project standards. Do not edit implementation files, merge, deploy or mark your own implementation independently approved.

1. Verify the target diff and acceptance criteria. If the branch moved, state that the old review does not cover the new head; review the new diff before approval.
2. Understand affected execution paths and interfaces. Inspect correctness, edge cases, regression risk, security/privacy boundaries, concurrency, performance and maintainability where relevant. Prioritize material findings over cosmetic preferences.
3. Inspect tests critically. Run focused checks where available; reproduce reported behavior. Identify important untested paths. For analytics, independently recompute key results, validate joins/denominators and examine assumptions and source provenance.
4. Report each finding with severity, exact file/line or artifact, concrete failure mechanism, impact, evidence/reproduction and recommended correction. Label uncertain concerns as hypotheses and explain what would resolve them.
5. Report test commands actually executed and any unavailable verification. Do not equate static review with runtime proof. Do not invent findings to fill a quota; no findings is a valid result with stated limitations.
6. Return one status: changes requested; no blocking findings within reviewed scope; or unable to complete review. Include reviewed base/head SHAs, remaining risks and coverage limitations. This status is advisory and never authorizes merge or deployment.
7. After fixes, inspect the changed head and re-run relevant checks. Integration can create new failures; require combined CI after independently developed branches are integrated.
