---
name: code-review
description: Review code changes for bugs, regressions, and missing tests. Use when asked to review a diff or pull request.
---

# Code review

Inspect the diff, changed files, and relevant callers and tests before drawing
conclusions. Follow repository instructions and keep the review focused on
issues introduced by the changes.

Report actionable findings with file paths and line numbers. Explain the
failure scenario and impact, prioritizing correctness, security, and regressions
over style. Distinguish confirmed problems from assumptions.

Run relevant tests when practical and report what was tested. If no actionable
findings remain, say so and note any testing gaps. Do not modify code unless
asked.
