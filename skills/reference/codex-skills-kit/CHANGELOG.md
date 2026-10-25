# Changelog

## Unreleased

## 0.3.0 - 2026-07-20

- Added `git-under-contention`, `gate-engineering`, `verify-honestly`, and `session-close` skills.
- Added deterministic Git-contention preflight with hermetic selftest.
- Expanded plugin from two-skill prompt loop to six-skill reliability loop.
- Updated `codex-prompt` with execution-context freshness and evidence contracts.
- Updated `retro-distill` with evidence thresholds and narrower artifact targeting.
- Added seeded validator selftests and CI execution for bundled script selftests.
- Extended validation to check changelog/plugin version consistency, Markdown anchors, and common secret patterns.
- Reframed README and contributor guidance around prompt-to-closeout lifecycle.

## 0.2.0 - 2026-06-09

- Added `task-types.json` as the source-of-truth registry for `codex-prompt` task scaffolds.
- Added golden prompt fixtures for every supported task type.
- Extended validation to check registry drift, golden fixture required blocks, and relative Markdown links.
- Updated contributor docs and PR checklist for task-type and fixture changes.

## 0.1.1 - 2026-06-08

- Added Codex app metadata for bundled skills.
- Added PR and issue templates for skill changes.
- Extended validation to check `agents/openai.yaml` drift.
- Added Codex plugin packaging and a repo marketplace catalog.
- Clarified plugin and direct-skill install paths in the README.

## 0.1.0 - 2026-06-05

- Initial release of `codex-prompt` and `retro-distill`.
- Added worked examples for the supported task types.
- Added standard-library skill validation script and CI workflow.
