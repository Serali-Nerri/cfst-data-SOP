# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

- `cfst-orchestrator/` is the parent orchestration skill source tree.
- `cfst-column-extractor/` is the child single-paper extraction skill source tree.
- `.codex/skills/cfst-orchestrator/` is the runtime-loaded parent skill path.
- `.codex/skills/cfst-column-extractor/` is the runtime-loaded child skill path.
- If you change either source skill, verify the matching runtime copy under `.codex/skills/` is still aligned before considering the task done.
- When modifying either skill, also consult `.claude/skills/skill-creator/SKILL.md` as the meta-reference for skill authoring. Use it to keep `SKILL.md` concise, move detailed rules into `references/`, and keep `agents/openai.yaml` aligned with the skill instructions and trigger wording.
- The parent skill owns orchestration and publishing:
  - `cfst-orchestrator/SKILL.md`: parent-agent orchestration contract
  - `cfst-orchestrator/scripts/*.py`: batch preparation, worktree isolation, sandbox execution, state updates, publication, and checkpointing
  - `cfst-orchestrator/agents/openai.yaml`: parent skill display metadata
- The child skill owns one-paper extraction policy:
  - `cfst-column-extractor/SKILL.md`: single-paper extraction contract
  - `cfst-column-extractor/references/extraction-rules.md`: scope and extraction rules for all CFST column ultimate-capacity data
  - `cfst-column-extractor/references/fc-basis-rules.md`: concrete-strength basis decision framework for `fco_mpa` / `fc_type`
  - `cfst-column-extractor/references/section_shapes.jpg`: visual reference for section groups and `r0_mm`
  - `cfst-column-extractor/references/cfst-extraction-schema.json`: machine-readable schema 1.0.0
  - `cfst-column-extractor/references/json-schema-requirements.md`: readable JSON shape, examples, inheritance rules, and validation expectations
  - `cfst-column-extractor/scripts/*.py`: sandbox-only extraction helpers such as validation and safe arithmetic
  - `cfst-column-extractor/agents/openai.yaml`: child skill display metadata

## Common commands

There is no package manager file, lint configuration, or automated unit-test framework checked into this repo. The checked-in operational commands are the Python scripts below, run from the repository root.

Bootstrap git so worktree-based execution can run:

```bash
python .codex/skills/cfst-orchestrator/scripts/bootstrap_git_repo.py \
  --repo-root . \
  --initial-empty-commit
```

Prepare a batch workspace from `processed/` PDFs:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_batch.py \
  --processed-root processed
```

Create and remove a per-paper worktree:

```bash
python .codex/skills/cfst-orchestrator/scripts/git_worktree_isolation.py create \
  --paper-dir '<paper_pdf_relpath>' \
  --skill-dir .codex/skills/cfst-column-extractor \
  --output-dir output/tmp/<paper_id>

python .codex/skills/cfst-orchestrator/scripts/git_worktree_isolation.py remove \
  --worktree-path '<worktree_path>' \
  --delete-branch
```

Validate one extracted output. This is the closest thing to a single-test command, and it must run through the sandbox wrapper:

```bash
python .codex/skills/cfst-orchestrator/scripts/worker_sandbox.py \
  --worktree-path <worktree_path> \
  --paper-dir-relpath <paper_pdf_relpath> \
  --skill-dir-relpath .codex/skills/cfst-column-extractor \
  --output-dir output/tmp/<paper_id> \
  --host-output-dir <output_host_path> \
  --cwd-mode workspace \
  -- \
  python3 .codex/skills/cfst-column-extractor/scripts/validate_single_output.py \
    --json-path output/tmp/<paper_id>/<paper_id>.json \
    --strict-rounding
```

Publish validated temp outputs into canonical output files:

```bash
python .codex/skills/cfst-orchestrator/scripts/publish_validated_output.py \
  --batch-manifest output/manifests/batch_manifest.json \
  --batch-state output/manifests/batch_state.json \
  --tmp-root output/tmp \
  --output-dir output/output \
  --publish-log output/logs/publish_log.jsonl \
  --extractor-skill-dir .codex/skills/cfst-column-extractor \
  --strict-rounding
```

Optional output-only checkpoint commit/push flow:

```bash
python .codex/skills/cfst-orchestrator/scripts/checkpoint_output_commits.py \
  --processed-count <n> \
  --output-dir output/output
```

## High-level architecture

- This repository is a skill bundle, not a normal Python package or application. Most project behavior lives in prompt/policy documents, while the Python scripts enforce orchestration boundaries and validation.
- `prepare_batch.py` scans `processed/` for PDFs whose filenames start with citation tags like `[A2-104]`, runs `pdfinfo`, and writes the parent-owned manifests:
  - `output/manifests/batch_manifest.json`
  - `output/manifests/worker_jobs.json`
  - `output/manifests/batch_state.json`
- Multi-paper extraction is a parent/worker pipeline. The parent reads `worker_jobs.json`, creates one isolated worktree per prepared paper, launches one sandboxed worker per paper, tracks lifecycle in `batch_state.json`, and only publishes outputs after validation succeeds.
- Isolation is enforced in two layers:
  - `git_worktree_isolation.py` creates a minimal per-paper git worktree
  - `worker_sandbox.py` runs the worker command under `bwrap`, mounting only the owned paper input read-only, the skill docs/scripts read-only, and the declared output directory read-write
- Worker-authoritative evidence is the owned rawdata bundle plus the owned PDF fallback. Default to `rawdata/[<paper_id>]/full.md` or the matching rawdata directory, open only referenced `images/` files as needed, use the PDF only when Markdown/images are missing, unreadable, incomplete, or conflicting, and use `content_list_v2.json` only for locating parsed/PDF blocks. The child skill files are `cfst-column-extractor/SKILL.md`, `cfst-column-extractor/references/extraction-rules.md`, `cfst-column-extractor/references/fc-basis-rules.md`, `cfst-column-extractor/references/section_shapes.jpg`, `cfst-column-extractor/references/cfst-extraction-schema.json`, and `cfst-column-extractor/references/json-schema-requirements.md`.
- Each worker writes exactly one temporary JSON artifact under `output/tmp/<paper_id>/`: `<paper_id>.json`.
- Published artifacts are canonical only after `publish_validated_output.py` copies validated temp JSON into `output/output/<paper_id>.json`. Workers should never write final outputs directly.
- `cfst-column-extractor/scripts/safe_calc.py` and `cfst-column-extractor/scripts/validate_single_output.py` are sandbox-only helpers. They require `CFST_SANDBOX=1`, so invoke them through `worker_sandbox.py`, not directly from the host shell.
- External runtime assumptions that are not vendored in the repo: a git repository with `HEAD`, `bwrap`/bubblewrap, `pdfinfo`, and Python available for validation.
- There is no README, no repo-local Cursor rule, and no Copilot instruction file in this repo. The source of truth is the parent `cfst-orchestrator/SKILL.md` for orchestration and the child `cfst-column-extractor/` files for one-paper extraction behavior.
