# Prompt engineering references

Sources are recorded in each SOURCE.json; upstream LICENSE files are retained. These community documents are references, not model weights or executable plugins. Only project-owned prompts/director.txt and prompts/youtube-publish.txt are sent as system instructions. Do not concatenate the entire kit into DeepSeek context.

Applied: explicit goal/context/constraints/output contract, source grounding, single final plan, narration-first shot mapping, evidence-bounded completion. Codex task-management instructions are for developers, not advertising content.

Offline checks validate wiring and schema regression only. tests/fixtures/prompt-quality-cases.json contains 10 qualitative evaluation cases; real DeepSeek comparisons were run on 2026-10-25; see docs/PROMPT_EVALUATION_2026-10-25.md for results and limits. Review continuity, source accuracy, visual alignment, pacing, diversity and CTA with the same cases before/after. Use real screenshots and audio for final production QA.
