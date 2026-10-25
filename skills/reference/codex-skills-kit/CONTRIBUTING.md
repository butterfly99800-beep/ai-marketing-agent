# Contributing to codex-skills-kit

Contributions of new failure-prevention rules, task types, fixtures, scripts, and skill improvements are welcome.

## Ground rules

- **Methodology is product.** New rule should prevent observed failure mode or encode repeatable success.
- **Keep it project-neutral.** Use fictional Acme Notes or generic placeholders; strip private names, infrastructure, paths, and incident identifiers.
- **Keep context lean.** Prefer concise core workflow and directly linked optional references.
- **Style:** en dashes (–) only, never em dashes (—) or double hyphens (`--`) as punctuation.

## Skill format

Every skill is a directory under `skills/` built on open [Agent Skills](https://agentskills.io) standard:

```text
skills/
  your-skill-name/
    SKILL.md            # required
    agents/openai.yaml  # recommended Codex app metadata
    references/         # optional deep detail
    scripts/            # optional deterministic helpers
    assets/             # optional output resources
```

### Required `SKILL.md` frontmatter

```yaml
---
name: your-skill-name
description: "Describe what skill does and exact requests or contexts that should trigger it."
metadata:
  version: 0.1.0
---
```

Rules enforced by `scripts/validate_skills.py`:

- Frontmatter opens and closes with `---`.
- `name` is kebab-case and matches directory.
- `description` is 20–1024 characters and contains triggering context.
- `metadata.version` is semantic version.
- Present `agents/openai.yaml` contains `display_name`, 25–64 character `short_description`, `default_prompt` mentioning `$your-skill-name`, valid optional brand color, and valid optional implicit-invocation policy.
- Plugin and marketplace metadata are coherent.
- `task-types.json`, examples, templates, and golden fixtures agree.
- Relative Markdown links and anchors resolve.
- Plugin version matches latest changelog release.
- Committed text contains no common token or private-key patterns.

Use imperative instructions in skill body. Add scripts when fragile procedure would otherwise be rewritten repeatedly. Deterministic scripts should expose hermetic `--selftest` when practical.

## Validation

```bash
python scripts/validate_skills.py --selftest
python scripts/validate_skills.py
```

Run any bundled script selftests changed by contribution.

## Adding task type

Add `<task-type>-example.md` under `examples/` and matching compact fixture under `fixtures/golden-prompts/`. Update in same change:

1. Corresponding `###` section in `skills/codex-prompt/SKILL.md`.
2. Matching sections in `skills/codex-prompt/references/prompt-templates.md`.
3. `task-types.json` registry entry.
4. README task-type table.

## Adding skill

1. Initialize package with current Codex `skill-creator` tooling.
2. Write narrow triggering description and concise workflow.
3. Generate `agents/openai.yaml` with default prompt naming `$skill-name`.
4. Add scripts, references, or assets only when skill needs them.
5. Update README inventory, plugin description/default prompts, and changelog.
6. Run repository validator and official skill quick validation.

## Pull requests

- Keep one logical change per pull request.
- Include commands and outputs proving changed gates fail on bad fixture and pass on good fixture.
- Update `.codex-plugin/plugin.json` and `CHANGELOG.md` when public plugin packaging changes.
- Keep CI green across skills, plugin, registry, fixtures, release metadata, links, and secret scan.

By contributing, you agree code contributions use MIT and skill, example, and fixture content uses CC BY 4.0.
