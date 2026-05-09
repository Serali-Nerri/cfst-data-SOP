---
name: cfst-orchestrator
description: Use only when explicitly specified by the user; orchestrates CFST batch extraction, publication, and optional CSV export.
---

# CFST Orchestrator

Use this skill as the parent orchestrator for multi-paper CFST column extraction. The parent owns package preparation, batch state, worker workspace/spec creation, sandbox command construction, retries, publication, and reporting. The child skill `.codex/skills/cfst-column-extractor` owns all one-paper extraction decisions and JSON authoring rules.

## Boundary

- The only input package root is `Pending/`.
- Unprepared packages are long directories such as `Pending/[A1-10] KATO ...pdf-<uuid>/`.
- Prepared packages are shortened directories such as `Pending/[A1-10]/`.
- A prepared package must contain `full.md`, `content_list_v2.json`, `images/`, and exactly one `*_origin.pdf`.
- Do not require or create `processed/[paper_id].pdf`; the package's `*_origin.pdf` is the owned fallback PDF.
- Do not send worktree paths, repo-relative PDF paths, output mount paths, or parent implementation details to workers.

## Workflow

1. Prepare each long Pending package before batch launch:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_rawdata_package.py \
  'Pending/[A1-10] long citation directory name'
```

Use `--dry-run` first when the supplied directory is ambiguous or already processed. If table images are not ready, `content_list_v2.json` table blocks do not match `full.md` HTML tables, or `Pending/[paper_id]` already exists unexpectedly, stop before worker launch and report the parent-owned input package issue.

For table replacement only, run:

```bash
python .codex/skills/cfst-orchestrator/scripts/replace_html_tables_with_images.py \
  'Pending/[A1-10]' \
  --in-place \
  --overwrite \
  --strict-count
```

2. Build the Pending-first batch manifests:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_batch.py \
  --pending-root Pending
```

Read `output/manifests/worker_jobs.json`. Process only entries whose `status` is `prepared`; all other statuses are parent-owned input/package failures or skips.
If `batch_state.json` already exists, `prepare_batch.py` preserves operational fields (`status`, `retry_count`, `validated`, `published`, `last_error`) for still-prepared papers. Use `--reset-state` only when intentionally starting state over.

3. For each prepared paper, generate the worker workspace, `worker_job_spec.json`, and `worker_brief.md`:

```bash
python .codex/skills/cfst-orchestrator/scripts/build_worker_job_spec.py \
  --worker-jobs output/manifests/worker_jobs.json \
  --paper-id <paper_id>
```

For retries, rerun the same command to build a fresh worker workspace and standard worker brief.

The script copies `Pending/[paper_id]/` and `.codex/skills/cfst-column-extractor/` into `tmp/cfst-worker-spaces/<paper_id>-<timestamp>-<pid>/`, writes parent-owned job metadata under `output/tmp/<paper_id>/`, and generates the complete sandbox and validation commands. Use the generated `worker_brief.md` as the worker prompt; do not hand-write long sandbox commands.

4. Spawn exactly one worker sub-agent per prepared paper. Cap concurrency at 5. Use the project default `fork_context=false` unless the user explicitly requests otherwise.

5. Immediately after launch, mark the paper `running` in `batch_state.json`.

6. Monitor workers with long waits. Do not interrupt a normally running worker just because a short poll timed out.

7. On worker completion, classify the returned status, update `batch_state.json`, retry only as allowed in `Failure Handling`, and remove the worker workspace when no longer needed:

```bash
python .codex/skills/cfst-orchestrator/scripts/cleanup_worker_workspace.py \
  --job-spec output/tmp/<paper_id>/worker_job_spec.json
```

8. Publish validated outputs only after prepared workers have finished or exhausted retry, then run checkpoints only if repository policy requires them.

9. After publication, ask the user whether to export the published JSON outputs to CSV unless the original user request already explicitly asked for CSV export. If yes, use `Optional CSV Export` below.

10. Report papers skipped before spawn, invalid parent-owned input packages, papers failed after retry, papers published to `output/output/`, and any CSV path generated.

## Worker Interface

Workers receive only the generated `worker_brief.md`. Its inputs should be limited to:

- `paper_id`
- `package_dir`
- `owned_pdf_path`
- `output_json_path`
- `sandbox_command_prefix`
- `validation_command`

The package contract supplies `full.md`, `images/`, and `content_list_v2.json` as fixed members under `package_dir`; do not repeat them as worker input fields.

The parent may keep richer metadata in `worker_job_spec.json`, including workspace paths, output mount paths, and sandbox arguments. Do not expose those fields as extraction inputs unless they are already embedded in a complete command string.

## State And Failure Handling

Use `python .codex/skills/cfst-orchestrator/scripts/update_batch_state.py --batch-state output/manifests/batch_state.json --paper-id <paper_id>` with these transitions:

- After launch: `--status running --validated false --published false --clear-last-error`
- After worker success and `output_json_path` exists: `--status ready_for_publication --validated true --published false --clear-last-error`
- After terminal failure: `--status failed --validated false --published false --increment-retry-count --last-error '<exact failure>'`

Handle returned worker status this way:

- `success`: verify the JSON exists, mark `ready_for_publication`, and publish later.
- `validation_failure` or `extraction_failure`: retry once with a fresh worker workspace.
- `input_contract_failure`: fix or mark the parent-owned Pending package before rerunning.
- `sandbox_failure`: fix the parent-owned command, path, mount, or startup issue before rerunning with a fresh worker workspace.
- `documentation_validator_mismatch`: stop and report the child documentation/validator mismatch.

## Publication

Publish after all prepared workers finish or exhaust their allowed retry:

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

If repository policy requires checkpoints, run:

```bash
python .codex/skills/cfst-orchestrator/scripts/checkpoint_output_commits.py \
  --checkpoint-count <published_plus_failed_count> \
  --output-dir output/output
```

## Optional CSV Export

Run this only after validated JSON files have been published, and only after the user confirms CSV export or explicitly requested it up front.

```bash
python .codex/skills/cfst-orchestrator/scripts/export_json_outputs_to_csv.py \
  --input-dir output/output \
  --output-csv output/output/cfst_specimens.csv
```

The CSV writer exports one row per specimen and resolves effective specimen data with the JSON contract inheritance order: `paper.defaults`, then `Group_X.shared`, then the specimen object. The default columns are:

```text
Ref.info., fco (MPa), fc_type, Specimen, fy (MPa), fcy150(Mpa), R (%), b (mm), h (mm), t (mm), r0 (mm), L (mm), e1 (mm), e2 (mm), Nexp (kN), Group, Material.steel, Material.concrete, loading mode, condition tags, condition notes
```

CSV field rules:

- `Ref.info.` is `first author,title,journal,year`.
- `fcy150(Mpa)` is intentionally blank for later normalized concrete-strength values.
- `Group` is written as `A`, `B`, `C`, or `D`.
- `Material.steel`, `Material.concrete`, and `loading mode` use the effective inherited value exactly as stored.
- `condition tags` joins effective `condition.tags` with `;`; `condition notes` uses effective `condition.notes`.
- The default CSV encoding is `utf-8-sig` so Chinese bibliographic text opens cleanly in common spreadsheet tools.
