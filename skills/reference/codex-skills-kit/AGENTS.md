# AGENTS.md – codex-skills-kit

Conventions for agents working in this repository. This is a content and tooling repo: reusable Codex workflow skills, plugin packaging, fixtures, and deterministic validation scripts. There is no application runtime.

## What this repo is

A package of Codex skills covering prompt delegation, Git contention, gate engineering, honest verification, session closeout, and self-distillation. It also ships as a Codex plugin. Methodology is product; keep its depth while stripping project-specific details.

## Layout

- `.codex-plugin/plugin.json` – plugin manifest bundling all folders under `skills/`.
- `.agents/plugins/marketplace.json` – repository marketplace catalog pointing at root plugin.
- `skills/<name>/SKILL.md` – skill instructions and triggering frontmatter.
- `skills/<name>/agents/openai.yaml` – optional Codex app metadata validated when present.
- `skills/<name>/scripts/` – optional deterministic helper with hermetic selftest when practical.
- `examples/<task-type>-example.md` – worked prompts on fictional Acme Notes project.
- `fixtures/golden-prompts/<task-type>.md` – compact canonical prompts validated against task registry.
- `task-types.json` – source-of-truth mapping task types to skills, templates, examples, and fixtures.
- `scripts/validate_skills.py` – skill, plugin, registry, fixture, release, link, and secret validator.
- `.github/workflows/validate-skills.yml` – CI validation on pushes and pull requests.

## Validate before committing

```bash
python scripts/validate_skills.py --selftest
python scripts/validate_skills.py
python skills/git-under-contention/scripts/contention_preflight.py --selftest
```

Green validation covers skill frontmatter, present Codex metadata, plugin and marketplace coherence, task registry, golden fixtures, local links and anchors, release metadata, secret patterns, and seeded validator failures.

## Conventions

- **Style:** en dashes (–) only in prose – never em dashes (—) or `--` as punctuation. Syntactic `--` in commands, SQL, and Markdown is fine.
- **Project-neutral:** examples and skills reference only Acme Notes or generic placeholders – no private project names, infrastructure, paths, or incident identifiers.
- **Progressive disclosure:** keep `SKILL.md` focused; move deep optional detail into directly linked `references/`.
- **Skill metadata:** frontmatter must match validator; `agents/openai.yaml` default prompt must name `$skill-name`.
- **Persistent gates:** prove new or changed gates with known-bad and known-good cases plus deterministic selftest.
- **Task-type changes move together:** update `codex-prompt`, prompt templates, worked example, golden fixture, `task-types.json`, and README table in one change.
- **Plugin inventory changes move together:** update plugin manifest description/default prompts, changelog version, README, and validation.
- **Diff discipline:** every changed line traces to task; avoid drive-by formatting.

## Do not

- Commit `AUDIT-REPORT.md` – scratch artifact is gitignored.
- Add network behavior to root validator.
- Add bundled runtime scripts when concise instructions are sufficient.
- Commit generated Python caches or local plugin cachebusters.

## Licensing

Code and scripts: MIT (`LICENSE`). Skill, example, and fixture content: CC BY 4.0 (`LICENSE-CONTENT`).
