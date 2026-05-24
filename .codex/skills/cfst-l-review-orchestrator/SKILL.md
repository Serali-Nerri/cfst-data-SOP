---
name: cfst-l-review-orchestrator
description: Use only when explicitly specified by the user; orchestrate batch L review across pre-extracted CFST paper packages.
---

# CFST L Review Orchestrator

Use this skill as the parent orchestrator for multi-paper CFST `L` review.
The parent owns batch state, worker workspace creation, validation,
publication, and the cross-paper summary. The child skill
`.codex/skills/cfst-l-reviewer` owns all per-paper review decisions and
`review.md` authoring rules.

## Boundary

- The only input package root is the caller-provided L-review Pending root
  (e.g. `/home/thelya/Work/cfst-data/Lreview/Pending`).
- Prepared packages are shortened directories such as
  `<pending_root>/[A1-1]/`.
- A prepared package must contain `full.md`, `images/`, `content_list_v2.json`,
  exactly one `*_origin.pdf`, and `<paper_id>.csv`.
- This skill does not prepare unprepared rawdata packages; if any are
  present, report them and stop. Use `cfst-orchestrator/prepare_rawdata_package.py`
  to prepare them first (outside this skill's scope).
- Do not send worker workspace paths or parent implementation details to
  workers beyond what the generated brief carries.

## Workflow

1. Build the L-review batch manifests:

```bash
python .codex/skills/cfst-l-review-orchestrator/scripts/prepare_l_review_batch.py \
  --pending-root /path/to/Lreview/Pending
```

Read `output/manifests/l_review_worker_jobs.json`. Process only entries
whose `status` is `prepared`; all other statuses are parent-owned input
issues.

If `l_review_batch_state.json` already exists, the script preserves
operational fields (`status`, `retry_count`, `validated`, `published`,
`last_error`) for still-prepared papers. Use `--reset-state` only to
intentionally restart.

2. For each prepared paper, generate the worker workspace, job spec, and
brief:

```bash
python .codex/skills/cfst-l-review-orchestrator/scripts/build_l_review_worker_spec.py \
  --worker-jobs output/manifests/l_review_worker_jobs.json \
  --paper-id <paper_id>
```

The script copies `<pending_root>/[paper_id]/` and
`.codex/skills/cfst-l-reviewer/` into
`tmp/cfst-l-review-worker-spaces/<paper_id>-<timestamp>-<pid>/`, creates an
empty `tmp/` subdirectory in the workspace for worker scratch, writes
parent-owned job metadata under `output/tmp/<paper_id>/`, and generates the
complete validation command. Use the generated `worker_brief.md` as the
worker prompt.

3. Spawn exactly one worker sub-agent per prepared paper. Cap concurrency at
5. Use the project default `fork_context=false` unless the user explicitly
requests otherwise.

4. Immediately after launch, mark the paper `running`:

```bash
python .codex/skills/cfst-l-review-orchestrator/scripts/update_batch_state.py \
  --batch-state output/manifests/l_review_batch_state.json \
  --paper-id <paper_id> \
  --status running --validated false --published false --clear-last-error
```

5. Monitor workers with long waits. Do not interrupt a normally running
worker just because a short poll timed out.

6. On worker completion, classify the returned status, update
`l_review_batch_state.json`, retry only as allowed in `State And Failure
Handling`, and remove the worker workspace when no longer needed:

```bash
python .codex/skills/cfst-l-review-orchestrator/scripts/cleanup_worker_workspace.py \
  --job-spec output/tmp/<paper_id>/l_review_worker_job_spec.json
```

7. Publish validated review outputs after all prepared workers have
finished or exhausted retry:

```bash
python .codex/skills/cfst-l-review-orchestrator/scripts/publish_l_review.py \
  --batch-manifest output/manifests/l_review_batch_manifest.json \
  --batch-state output/manifests/l_review_batch_state.json \
  --tmp-root output/tmp \
  --output-dir output/output/L-review \
  --publish-log output/logs/l_review_publish_log.jsonl \
  --reviewer-skill-dir .codex/skills/cfst-l-reviewer
```

8. Aggregate the cross-paper summary:

```bash
python .codex/skills/cfst-l-review-orchestrator/scripts/aggregate_review_summary.py \
  --output-dir output/output/L-review \
  --summary-md output/output/L-review/_summary.md \
  --summary-csv output/output/L-review/_summary.csv
```

9. Report papers reviewed, papers requiring change, totals, and any
papers that failed after retry.

## Worker Interface

Workers receive only the generated `worker_brief.md`. Its inputs are:

- `paper_id`
- `package_dir`
- `owned_pdf_path`
- `extracted_csv_path`
- `output_review_path`
- `recommended_csv_path`
- `workspace_tmp_dir`
- `validation_command`

The package contract supplies `full.md`, `images/`, `content_list_v2.json`,
and `<paper_id>.csv` as fixed members under `package_dir`.

The parent may keep richer metadata in `l_review_worker_job_spec.json`. Do
not expose those fields as inputs unless they are already embedded in a
complete command string.

## State And Failure Handling

Use `update_batch_state.py` with these transitions:

- After launch: `--status running --validated false --published false --clear-last-error`
- After worker success and `output_review_path` exists: `--status ready_for_publication --validated true --published false --clear-last-error`
- After terminal failure: `--status failed --validated false --published false --increment-retry-count --last-error '<exact failure>'`

Handle returned worker status this way:

- `success`: verify the review file exists, mark `ready_for_publication`, publish later.
- `validation_failure` or `review_failure`: retry once with a fresh worker workspace.
- `input_contract_failure`: fix or mark the parent-owned input issue before rerunning.
- `documentation_validator_mismatch`: stop and report the child documentation/validator mismatch.

## Publication

`publish_l_review.py` re-runs the child validator against the worker
output, then atomically copies the validated `review.md` and (if present)
`<paper_id>_recommended.csv` from `output/tmp/<paper_id>/` to
`output/output/L-review/<paper_id>/`. It records each result in
`output/logs/l_review_publish_log.jsonl` and updates batch state to
`published` or `publish_failed`.

## Aggregation

`aggregate_review_summary.py` scans `output/output/L-review/*/review.md`,
parses each Summary section, and writes:

- `_summary.md`: ranked Markdown report (papers needing change first).
- `_summary.csv`: one row per paper with `paper_id, reviewed, OK, CHANGE, UNDETERMINED, recommended_csv_present`.
