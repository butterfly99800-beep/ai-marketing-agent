# codex-skills-kit

**A reliability toolkit for serious OpenAI Codex work, shipped as a plugin and portable [Agent Skills](https://developers.openai.com/codex/skills).**

[![License: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](./LICENSE)
[![Content: CC BY 4.0](https://img.shields.io/badge/content-CC--BY--4.0-lightgrey.svg)](./LICENSE-CONTENT)
[![Tag](https://img.shields.io/github/v/tag/TAKEOFF69/codex-skills-kit?sort=semver)](https://github.com/TAKEOFF69/codex-skills-kit/tags)
[![Stars](https://img.shields.io/github/stars/TAKEOFF69/codex-skills-kit?style=social)](https://github.com/TAKEOFF69/codex-skills-kit/stargazers)

Most prompt libraries stop at prompt. Real agent failures happen later: wrong worktree, shared index contamination, checks that never caught anything, build results presented as runtime proof, and finished sessions stranded on one disk.

This kit packages a production-tested operating loop for Codex:

```text
prompt → isolate → execute → gate → verify → close → distill ↺
```

Each workflow lives in focused `SKILL.md`, loads through progressive disclosure, and carries only rules another Codex run needs to do work.

## Skills

| Skill | Job | Trigger example |
|---|---|---|
| **[codex-prompt](./skills/codex-prompt/)** | Generate grounded delegation prompts across six task types | "Write a Codex fix prompt" |
| **[git-under-contention](./skills/git-under-contention/)** | Preserve work when agents share branches, indexes, or worktrees | "Commit without touching other sessions" |
| **[gate-engineering](./skills/gate-engineering/)** | Build durable checks with seeded red and green proof | "Add a gate for this defect class" |
| **[verify-honestly](./skills/verify-honestly/)** | Match completion claims to execution-context evidence | "Is this actually fixed?" |
| **[session-close](./skills/session-close/)** | Reconcile, verify, preserve, and hand off session state | "Close out this session" |
| **[retro-distill](./skills/retro-distill/)** | Turn observed successes and failures into reusable rules | "What did we learn?" |

Together they cover work before, during, and after code generation.

`codex-prompt` task contract is checked into [`task-types.json`](./task-types.json). It maps every supported type to skill section, prompt template, worked example, and golden fixture under [`fixtures/golden-prompts/`](./fixtures/golden-prompts/). CI catches drift between methodology and prompts users copy.

## What changed in v0.3

v0.2 introduced task registry and golden prompt fixtures. v0.3 adds four reliability layers distilled from sustained production work:

- **Execution context is part of proof.** Local is not production, mock data is not live data, and build success is not browser pass.
- **A gate must prove it can fail.** Persistent checks ship known-bad fixture, known-good twin, and repeatable selftest.
- **Shared Git state is contested state.** Exact path staging, worktree isolation, remote durability, and explicit ownership replace cleanup-by-instinct.
- **Closeout is an engineering phase.** Docs, generated artifacts, evidence, commits, pushes, and residual risk are reconciled before session disappears.
- **Retros update smallest authoritative artifact.** Repeated workflow knowledge belongs in skills or executable gates, not ever-growing passive notes.

Project names, private infrastructure, and domain-specific rules were removed. Methods remain.

## Install

### Plugin package

Recommended path bundles all six skills:

```bash
codex plugin marketplace add TAKEOFF69/codex-skills-kit
```

Open `/plugins`, switch to **Codex Skills Kit** marketplace, install **Codex Skills Kit**, and start a new thread so Codex loads updated bundle.

For local clone:

```bash
codex plugin marketplace add ./path/to/codex-skills-kit
```

### Individual skills

Install any skill directly from GitHub tree URL:

```text
$skill-installer install https://github.com/TAKEOFF69/codex-skills-kit/tree/main/skills/codex-prompt
$skill-installer install https://github.com/TAKEOFF69/codex-skills-kit/tree/main/skills/git-under-contention
$skill-installer install https://github.com/TAKEOFF69/codex-skills-kit/tree/main/skills/gate-engineering
$skill-installer install https://github.com/TAKEOFF69/codex-skills-kit/tree/main/skills/verify-honestly
$skill-installer install https://github.com/TAKEOFF69/codex-skills-kit/tree/main/skills/session-close
$skill-installer install https://github.com/TAKEOFF69/codex-skills-kit/tree/main/skills/retro-distill
```

Or clone and copy selected folders into supported scope:

- Repo-scoped: `./.agents/skills/`
- User-scoped: `$HOME/.agents/skills/`
- Installer default: `$CODEX_HOME/skills`, normally `$HOME/.codex/skills`

```bash
git clone https://github.com/TAKEOFF69/codex-skills-kit
cp -r codex-skills-kit/skills/verify-honestly .agents/skills/
```

Trigger skills implicitly with matching request or explicitly with `$skill-name`.

## Core methodology

### 1. Define destination

Every delegated task starts with:

```text
Goal: <what changes>
Success means: <observable criteria>
Stop when: <completion or safe stop condition>
```

Then it adds context, constraints, assumptions, invariant, risk gate, repository mismatch handling, and exact done-when evidence.

### 2. Preserve execution state

Parallel agents cannot treat checkout as private workspace. `git-under-contention` detects deterministic contention signals and enforces explicit ownership:

```bash
python skills/git-under-contention/scripts/contention_preflight.py --selftest
python skills/git-under-contention/scripts/contention_preflight.py --mine skills/my-skill
```

### 3. Make quality nets prove themselves

`gate-engineering` separates ordinary feature tests from standing repository gates:

```text
seeded defect → observed red → fixed twin → observed green → corpus run
```

It also checks empty-set traps, mutable snapshots, read-path bypasses, and stale baselines.

### 4. Bound claims by evidence

`verify-honestly` uses five named levels:

```text
code read → local tests → browser pass → live data check → production smoke
```

Highest applicable level is reported per shipped item with anything still deploy-gated or inaccessible.

### 5. Leave work durable and improve loop

`session-close` reconciles state, documentation, generated artifacts, verification, commits, pushes, and handoff. `retro-distill` promotes supported lessons into right active surface: prompt skill, workflow skill, executable gate, `AGENTS.md`, or project memory.

## codex-prompt task types

| Fix | Build | Ops/Tuning | Audit | Refactor | PR-series |
|---|---|---|---|---|---|
| mandatory diagnosis before patch | feature from spec | live baseline and before/after evidence | read-only verdict | inventory before structure change | ordered, dependency-aware PRs |

See [`examples/`](./examples/) for full prompts on fictional Acme Notes project.

## Repository structure

```text
codex-skills-kit/
├── .codex-plugin/plugin.json
├── .agents/plugins/marketplace.json
├── AGENTS.md
├── skills/
│   ├── codex-prompt/
│   ├── gate-engineering/
│   ├── git-under-contention/
│   ├── retro-distill/
│   ├── session-close/
│   └── verify-honestly/
├── examples/
├── fixtures/golden-prompts/
├── task-types.json
├── scripts/validate_skills.py
├── CHANGELOG.md
└── .github/workflows/validate-skills.yml
```

## Validate

```bash
python scripts/validate_skills.py --selftest
python scripts/validate_skills.py
python skills/git-under-contention/scripts/contention_preflight.py --selftest
```

## Contributing

Contributions should prevent observed failure classes, remain project-neutral, and keep skill bodies concise. Validator covers skills, plugin metadata, task registry, golden fixtures, release metadata, links, and secret patterns. See [CONTRIBUTING.md](./CONTRIBUTING.md) and [AGENTS.md](./AGENTS.md).

## License

- Code and scripts: [MIT](./LICENSE)
- Skill, example, and fixture content: [CC BY 4.0](./LICENSE-CONTENT)

Use it, fork it, and adapt it to your stack. Attribution appreciated.
