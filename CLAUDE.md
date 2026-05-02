# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Repository Layout

- `.codex/skills/cfst-orchestrator/` is the runtime-loaded parent orchestration skill.
- `.codex/skills/cfst-column-extractor/` is the runtime-loaded child single-paper extraction skill.
- The parent owns `Pending/` package preparation, batch manifests/state, worker workspace/spec generation, sandbox execution, publication, and checkpointing.
- The child owns one-paper CFST column extraction policy, reference rules, JSON authoring, safe arithmetic, and validation behavior.
- When modifying either skill, keep `SKILL.md` concise and keep `agents/openai.yaml` aligned with the skill instructions and trigger wording.

## Current Workflow

The current orchestration model is Pending-package-first. Do not introduce a separate `processed/[paper_id].pdf` staging requirement.

Input packages live under:

```text
Pending/
```

Unprepared packages use long parser/citation directory names, for example:

```text
Pending/[A1-10] KATO B. Column curves ...pdf-<uuid>/
```

Prepared packages are shortened to:

```text
Pending/[A1-10]/
```

A prepared package must contain:

```text
full.md
content_list_v2.json
images/
*_origin.pdf
```

## Common Commands

Prepare one Pending package:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_rawdata_package.py \
  'Pending/[A1-10] long citation directory name'
```

Prepare batch manifests from Pending packages:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_batch.py \
  --pending-root Pending
```

This preserves existing `batch_state.json` operational fields for still-prepared papers. Pass `--reset-state` only when intentionally restarting state tracking.

Build one worker workspace, job spec, and worker brief:

```bash
python .codex/skills/cfst-orchestrator/scripts/build_worker_job_spec.py \
  --worker-jobs output/manifests/worker_jobs.json \
  --paper-id A1-10
```

On retry, regenerate the brief with the exact previous failure:

```bash
python .codex/skills/cfst-orchestrator/scripts/build_worker_job_spec.py \
  --worker-jobs output/manifests/worker_jobs.json \
  --paper-id A1-10 \
  --retry-reason '<exact failure>'
```

The generated worker prompt is:

```text
output/tmp/<paper_id>/worker_brief.md
```

Validate one extracted output through the generated `validation_command` in `worker_brief.md`. The sandbox command uses `worker_sandbox.py`, which mounts the worker package read-only, the child skill read-only, and the declared output directory read-write.

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

Remove generated worker workspaces after the parent no longer needs them:

```bash
python .codex/skills/cfst-orchestrator/scripts/cleanup_worker_workspace.py \
  --job-spec output/tmp/<paper_id>/worker_job_spec.json
```

Optional output-only checkpoint commit/push flow:

```bash
python .codex/skills/cfst-orchestrator/scripts/checkpoint_output_commits.py \
  --checkpoint-count <published_plus_failed_count> \
  --output-dir output/output
```

## Architecture Notes

- `prepare_batch.py` scans `Pending/`, not `processed/`.
- `worker_jobs.json` is package-first: it records package paths, owned `*_origin.pdf`, output JSON path, and readiness status.
- `build_worker_job_spec.py` creates a per-paper workspace under `tmp/cfst-worker-spaces/`, copies the prepared package and child skill there, writes `worker_job_spec.json`, and writes a concise `worker_brief.md`.
- Worker briefs should expose only `paper_id`, `package_dir`, `owned_pdf_path`, `output_json_path`, `sandbox_command_prefix`, and `validation_command`.
- `full.md`, `images/`, and `content_list_v2.json` are fixed members under `package_dir`; do not repeat them as worker input fields.
- Parent-only details such as workspace paths, mount paths, and sandbox arguments belong in `worker_job_spec.json`, not in extraction inputs.
- `cleanup_worker_workspace.py` removes only generated workspaces recorded in `worker_job_spec.json` and rejects paths outside `tmp/cfst-worker-spaces/`.
- Published artifacts are canonical only after `publish_validated_output.py` copies validated temp JSON into `output/output/<paper_id>.json`.
- `cfst-column-extractor/scripts/safe_calc.py` and `cfst-column-extractor/scripts/validate_single_output.py` require `CFST_SANDBOX=1`; invoke them through the parent-provided sandbox command, not directly from the host shell during worker extraction.
