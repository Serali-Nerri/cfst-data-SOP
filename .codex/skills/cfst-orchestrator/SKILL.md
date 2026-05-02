---
name: cfst-orchestrator
description: Orchestrate multi-paper CFST column extraction batches from `processed/` PDFs and prepared rawdata packages using isolated per-paper workers, batch manifests/state, retry handling, sandboxed validation, and publication. Use when Codex needs to preprocess rawdata directories, prepare a batch, launch or monitor worker sub-agents, repair parent-side orchestration failures, publish validated outputs, or report overall extraction progress. Delegate actual one-paper extraction to `cfst-column-extractor`.
---

# CFST Orchestrator

Use this skill as the parent orchestrator for multi-paper CFST column extraction. Keep this file to orchestration entry points, ownership boundaries, worker contracts, validation handoff, retry handling, publication, and reporting.

## Boundary

The parent owns PDF/rawdata resolution, rawdata preparation, batch state, worktree isolation, sandbox command construction, worker launch/monitoring, retries, publication, and final reporting.

The child skill `.codex/skills/cfst-column-extractor` owns one-paper extraction: source-use policy, extraction scope, field rules, JSON authoring rules, validator-repair rules, and schema 2.0.0-draft meaning.

Do not duplicate child extraction policy, source-priority policy, field rules, schema details, or child reference-file lists in this parent skill or in worker briefs. The parent provides resolved paths and exact commands; the child controls its own resources.

## Inputs And State

- `processed/` contains source PDFs whose filenames start with citation tags like `[A2-104]`.
- Rawdata roots are user-provided and not necessarily named `rawdata`; use the user-specified root and paper directory exactly.
- Prepared rawdata paper packages should be shortened to `[<paper_id>]` before worker use.
- `output/manifests/worker_jobs.json` is authoritative for readiness, `paper_pdf_relpath`, and `worker_output_json_path`.
- `output/manifests/batch_state.json` is authoritative for launch, validation, retry, publication, and failure state.
- Workers write temp JSON under `output/tmp/<paper_id>/`; only the parent publishes canonical JSON into `output/output/`.

## Workflow

1. Ensure the repository has a git `HEAD`; initialize it once if needed:

```bash
python .codex/skills/cfst-orchestrator/scripts/bootstrap_git_repo.py \
  --repo-root . \
  --initial-empty-commit
```

2. Prepare user-provided rawdata packages before worker launch:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_rawdata_package.py \
  '<rawdata-root>/[A1-1] long citation directory name'
```

Use `--dry-run` first when the supplied directory is ambiguous or already processed. If table images are not ready, `content_list_v2.json` table blocks do not match `full.md` HTML tables, or the shortened target directory already exists unexpectedly, stop before worker launch and report the parent-owned input package issue.

For table replacement only, run `python .codex/skills/cfst-orchestrator/scripts/replace_html_tables_with_images.py '<rawdata-root>/[A1-1]' --in-place --overwrite --strict-count`.

3. Prepare the batch workspace:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_batch.py \
  --processed-root processed
```

4. Read `output/manifests/worker_jobs.json`. Process only entries whose `status` is `prepared`; use `paper_pdf_relpath` and `worker_output_json_path` exactly as written.

5. Create one isolated worktree per prepared paper and record `worktree_path`, `branch`, `paper_rel`, `output_dir`, `output_host_path`, and `skill_rel`:

```bash
python .codex/skills/cfst-orchestrator/scripts/git_worktree_isolation.py create \
  --paper-dir '<paper_pdf_relpath>' \
  --skill-dir .codex/skills/cfst-column-extractor \
  --output-dir output/tmp/<paper_id>
```

6. Spawn exactly one worker sub-agent per prepared paper. Cap concurrency at 5. Each worker owns one paper, one worktree, and one temp JSON path. Use the project default `fork_context=false` unless the user explicitly requests otherwise.

7. Build the worker command strings in `Worker Commands`, send the worker brief in `Worker Brief Contract`, and immediately mark that paper `running` in `batch_state.json`.

8. Monitor workers with long waits. Do not interrupt a normally running worker just because a short poll timed out.

9. On worker completion, classify the returned status, update `batch_state.json`, retry only as allowed in `Failure Handling`, and always remove the finished worktree.

10. Publish validated outputs only after prepared workers have finished or exhausted retry, then run checkpoints only if repository policy requires them.

11. Report papers skipped before spawn, failed after retry, and published to `output/output/`.

## Worker Commands

Build and pass these fully expanded strings to the worker after placeholder substitution.

`sandbox_command_prefix`:

```bash
python .codex/skills/cfst-orchestrator/scripts/worker_sandbox.py \
  --worktree-path <worktree_path> \
  --paper-dir-relpath <paper_pdf_relpath> \
  --skill-dir-relpath .codex/skills/cfst-column-extractor \
  --output-dir output/tmp/<paper_id> \
  --host-output-dir <output_host_path> \
  --cwd-mode workspace \
  --
```

`validation_command`: the same sandbox prefix followed by:

```bash
python3 .codex/skills/cfst-column-extractor/scripts/validate_single_output.py \
  --json-path output/tmp/<paper_id>/<paper_id>.json \
  --strict-rounding
```

The child must run `validation_command` exactly as provided and must not reconstruct worktree paths, mount paths, or validator arguments.

## Worker Brief Contract

Use this template. Fill every placeholder before spawning the worker.

```text
Own exactly one CFST paper.
Use $cfst-column-extractor at `.codex/skills/cfst-column-extractor`.
Read that child skill and follow it for all extraction decisions and JSON authoring rules.

Inputs:
- paper_id: <paper_id>
- worktree_path: <worktree_path>
- paper_pdf_relpath: <paper_pdf_relpath>
- paper_pdf_path: <absolute_host_path_to_pdf>
- output_dir: output/tmp/<paper_id>
- output_host_path: <output_host_path>
- temp_json_workspace_path: output/tmp/<paper_id>/<paper_id>.json
- temp_json_host_path: <worker_output_json_path_from_worker_jobs.json>
- rawdata_status: prepared | unavailable | invalid
- rawdata_dir: <parent-resolved prepared rawdata dir, or unavailable>
- full_md_path: <rawdata_dir>/full.md, or unavailable
- images_dir: <rawdata_dir>/images, or unavailable
- content_list_path: <rawdata_dir>/content_list_v2.json, or unavailable
- sandbox_command_prefix: <fully expanded sandbox command prefix>
- validation_command: <fully expanded validation command>

Parent-owned constraints:
- Work only on this one paper.
- Do not use `.codex/skills/cfst-orchestrator/SKILL.md` as extraction policy.
- Do not search unrelated rawdata directories, processed PDFs, prior outputs, or runs.
- Write exactly one JSON file to `temp_json_host_path`; write no secondary extraction artifacts.
- Run `validation_command` exactly as given after writing JSON.
- Repair once only for documented child-skill JSON/data validation rules, then rerun the same validator command.
- Return sandbox path, mount, or startup failures to the parent.
- Report undocumented validator rules as documentation/validator mismatches.

Return exactly:
- paper_id
- temp_json path (`temp_json_workspace_path`)
- status: success | input_contract_failure | extraction_failure | validation_failure | sandbox_failure | documentation_validator_mismatch
- validation pass/fail
- failure reason if any
```

## State And Failure Handling

Use `python .codex/skills/cfst-orchestrator/scripts/update_batch_state.py --batch-state output/manifests/batch_state.json --paper-id <paper_id>` with these parent-owned transitions:

- After launch: `--status running --validated false --published false --clear-last-error`
- After worker success and temp JSON exists: `--status ready_for_publication --validated true --published false --clear-last-error`
- After terminal failure: `--status failed --validated false --published false --increment-retry-count --last-error '<exact failure>'`

Handle returned worker status this way:

- `success`: verify the temp JSON exists, mark `ready_for_publication`, and publish later.
- `validation_failure` or `extraction_failure`: retry once on a fresh worktree with the exact failure reason in the new worker brief.
- `input_contract_failure`: fix or mark the parent-owned input package before rerunning; do not ask the child to search for replacement rawdata.
- `sandbox_failure`: fix the parent-owned command, path, mount, or startup issue before rerunning on a fresh worktree.
- `documentation_validator_mismatch`: stop and report the child documentation/validator mismatch.

Always remove each finished worktree:

```bash
python .codex/skills/cfst-orchestrator/scripts/git_worktree_isolation.py remove \
  --worktree-path '<worktree_path>' \
  --delete-branch
```

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
  --processed-count <published_plus_failed_count> \
  --output-dir output/output
```

Final reports must include skipped-before-spawn papers, invalid parent-owned input packages, papers failed after retry, and papers published to `output/output/`.
