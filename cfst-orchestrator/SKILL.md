---
name: cfst-orchestrator
description: Orchestrate multi-paper CFST column extraction batches from `processed/` PDFs using isolated per-paper workers, batch manifests/state, retry handling, sandboxed validation, and publication. Use when Codex needs to prepare a batch, launch or monitor worker sub-agents, repair parent-side orchestration failures, publish validated outputs, or report overall extraction progress. Delegate actual one-paper extraction to `cfst-column-extractor`.
---

# CFST Orchestrator

Use this skill as the parent orchestrator. Keep the parent focused on batch preparation, worker ownership, retries, publication, and reporting. Delegate actual one-paper extraction to `$cfst-column-extractor` at `.codex/skills/cfst-column-extractor`.

## Background

- `processed/` contains source PDFs whose filenames start with citation tags like `[A2-104]`.
- `output/manifests/worker_jobs.json` is the source of truth for per-paper readiness, `paper_pdf_relpath`, and `worker_output_json_path`.
- Workers write temp artifacts under `output/tmp/<paper_id>/`; only the parent publishes canonical JSON into `output/output/`.
- The child skill owns the one-paper extraction contract, scratch YAML contract, schema rules, and validator logic. Do not duplicate extraction policy in the parent.

## Workflow

1. Ensure the repository has a git `HEAD`. If it does not, initialize it once:

```bash
python .codex/skills/cfst-orchestrator/scripts/bootstrap_git_repo.py \
  --repo-root . \
  --initial-empty-commit
```

2. Prepare the batch workspace:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_batch.py \
  --processed-root processed
```

3. Read `output/manifests/worker_jobs.json`. Process only papers whose `status` is `prepared`. Use `paper_pdf_relpath` and `worker_output_json_path` exactly as written; do not reconstruct them from `paper_id`.

4. Create one isolated worktree per prepared paper:

```bash
python .codex/skills/cfst-orchestrator/scripts/git_worktree_isolation.py create \
  --paper-dir '<paper_pdf_relpath>' \
  --skill-dir .codex/skills/cfst-column-extractor \
  --output-dir output/tmp/<paper_id>
```

Record at least:

- `worktree_path`
- `branch`
- `paper_rel`
- `output_dir`
- `output_host_path`
- `skill_rel`

5. Spawn exactly one worker sub-agent per paper. Cap concurrency at 5. The worker owns only one paper, one worktree, and one temp JSON path.

6. Use this worker brief template:

```text
Own exactly one CFST paper.
Use $cfst-column-extractor at `.codex/skills/cfst-column-extractor`.

Inputs:
- paper_id: <paper_id>
- worktree_path: <worktree_path>
- paper_pdf_relpath: <paper_pdf_relpath>
- paper_pdf_path: <absolute_host_path_to_pdf>
- output_dir: output/tmp/<paper_id>
- output_host_path: <output_host_path>
- temp_json_workspace_path: output/tmp/<paper_id>/<paper_id>.json
- temp_json_host_path: <worker_output_json_path_from_worker_jobs.json>

Authoritative files inside the worktree:
- .codex/skills/cfst-column-extractor/SKILL.md
- .codex/skills/cfst-column-extractor/references/extraction-rules.md
- .codex/skills/cfst-column-extractor/references/single-flow.md

Parent-owned constraints:
- Work only on this one paper.
- Do not use `.codex/skills/cfst-orchestrator/SKILL.md` as extraction policy.
- Write exactly one JSON file on disk to `temp_json_host_path`.
- Build exactly one scratch YAML at `output/tmp/<paper_id>/_scratch/extraction_draft.yaml`.
- Use the child skill files above as the authoritative extraction contract.
- Run sandbox validation with:
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
      --scratch-yaml-path output/tmp/<paper_id>/_scratch/extraction_draft.yaml \
      --strict-rounding
- If validation fails for schema, data, or evidence reasons, repair once and rerun the same validator command.
- If the sandbox reports a path, mount, or startup failure, stop and return that failure to the parent.

Return exactly:
- paper_id
- temp_json path (`temp_json_workspace_path`)
- validation pass/fail
- failure reason if any
```

7. Immediately after launch, mark the paper `running`:

```bash
python .codex/skills/cfst-orchestrator/scripts/update_batch_state.py \
  --batch-state output/manifests/batch_state.json \
  --paper-id <paper_id> \
  --status running \
  --validated false \
  --published false \
  --clear-last-error
```

8. Monitor active workers with long waits. Do not interrupt a normally running worker just because a short poll timed out.

9. When a worker finishes:

- if it succeeded and the temp JSON exists, mark `ready_for_publication`
- if it failed for schema, evidence, or extraction-decision reasons, retry once on a fresh worktree with the exact failure
- if it failed for path, mount, or sandbox startup reasons, fix the parent-side command or binding first, then rerun on a fresh worktree

Success state update:

```bash
python .codex/skills/cfst-orchestrator/scripts/update_batch_state.py \
  --batch-state output/manifests/batch_state.json \
  --paper-id <paper_id> \
  --status ready_for_publication \
  --validated true \
  --published false \
  --clear-last-error
```

Failure state update:

```bash
python .codex/skills/cfst-orchestrator/scripts/update_batch_state.py \
  --batch-state output/manifests/batch_state.json \
  --paper-id <paper_id> \
  --status failed \
  --validated false \
  --published false \
  --increment-retry-count \
  --last-error '<exact failure>'
```

10. Always remove each finished worktree:

```bash
python .codex/skills/cfst-orchestrator/scripts/git_worktree_isolation.py remove \
  --worktree-path '<worktree_path>' \
  --delete-branch
```

11. After all prepared papers finish, publish validated outputs with the child skill validator:

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

12. If repository policy requires checkpoints, run them only after publication:

```bash
python .codex/skills/cfst-orchestrator/scripts/checkpoint_output_commits.py \
  --processed-count <published_plus_failed_count> \
  --output-dir output/output
```

13. In the final report, distinguish:

- papers skipped before spawn because `worker_jobs.json.status != prepared`
- papers that failed after retry
- papers successfully published to `output/output/`

## Use These Scripts

- `scripts/bootstrap_git_repo.py`: initialize a repo and optional empty commit so worktree execution can start
- `scripts/prepare_batch.py`: discover processed PDFs and write manifests/state for parent orchestration
- `scripts/git_worktree_isolation.py`: create and remove per-paper worktrees that contain the owned paper plus the child extraction skill
- `scripts/worker_sandbox.py`: run one worker command under `bwrap`, mounting the owned paper read-only, the child skill read-only, and the declared output directory read-write
- `scripts/update_batch_state.py`: update one paper entry in `batch_state.json`
- `scripts/publish_validated_output.py`: revalidate and publish temp outputs using the child skill validator
- `scripts/checkpoint_output_commits.py`: commit or push published outputs at fixed intervals when repository policy requires it
