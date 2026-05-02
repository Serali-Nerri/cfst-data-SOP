---
name: cfst-orchestrator
description: Orchestrate multi-paper CFST column extraction batches from `processed/` PDFs and prepared rawdata packages using isolated per-paper workers, batch manifests/state, retry handling, sandboxed validation, and publication. Use when Codex needs to preprocess rawdata directories, prepare a batch, launch or monitor worker sub-agents, repair parent-side orchestration failures, publish validated outputs, or report overall extraction progress. Delegate actual one-paper extraction to `cfst-column-extractor`.
---

# CFST Orchestrator

Use this skill as the parent orchestrator. Keep the parent focused on batch preparation, worker ownership, retries, publication, and reporting. Delegate actual one-paper extraction to `$cfst-column-extractor` at `.codex/skills/cfst-column-extractor`.

## Background

- `processed/` contains source PDFs whose filenames start with citation tags like `[A2-104]`.
- User-provided extraction source directories are usually under a rawdata root whose name is not fixed. Each paper package should be shortened to `[<paper_id>]` before workers use it.
- `output/manifests/worker_jobs.json` is the source of truth for per-paper readiness, `paper_pdf_relpath`, and `worker_output_json_path`.
- Workers write temp artifacts under `output/tmp/<paper_id>/`; only the parent publishes canonical JSON into `output/output/`.
- The child skill owns the one-paper extraction workflow, extraction rules, schema rules, and validator logic. Do not duplicate extraction policy in the parent.

## Child Extraction Contract

This parent skill has no `references/` contract. Keep all parent orchestration guidance in this `SKILL.md`; send workers to the child skill for one-paper extraction.

Use `.codex/skills/cfst-column-extractor/SKILL.md` for the worker execution and validation workflow. The child workflow is rawdata-first: use `rawdata/[<paper_id>]/full.md` or the matching rawdata directory by default, open referenced `images/` only as needed, use the PDF only as fallback/conflict resolver, and use `content_list_v2.json` only for locating parsed/PDF blocks.

Use the child reference files for extraction decisions and schema requirements:

- `.codex/skills/cfst-column-extractor/references/extraction-rules.md`
- `.codex/skills/cfst-column-extractor/references/fc-basis-rules.md`
- `.codex/skills/cfst-column-extractor/references/section_shapes.jpg`
- `.codex/skills/cfst-column-extractor/references/cfst-extraction-schema.json`
- `.codex/skills/cfst-column-extractor/references/JSON_contract.md`

## Workflow

1. Ensure the repository has a git `HEAD`. If it does not, initialize it once:

```bash
python .codex/skills/cfst-orchestrator/scripts/bootstrap_git_repo.py \
  --repo-root . \
  --initial-empty-commit
```

2. If the user provides rawdata extraction directories, preprocess each paper package before spawning workers. The rawdata root name may differ from `rawdata`; use the user-specified root and paper directory exactly.

Run the package preparation script on the long paper directory, for example:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_rawdata_package.py \
  '<rawdata-root>/[A1-1] long citation directory name'
```

This script performs the parent-owned rawdata cleanup:

- renames the paper directory to `[<paper_id>]`, for example `[A1-1]`
- crops table images from `content_list_v2.json` + `*_origin.pdf`, names them from the printed table captions, writes them under `images/`, and replaces `full.md` HTML `<table>...</table>` blocks with Markdown image links
- includes table footnotes below the table in the crop when `content_list_v2.json` marks a table footnote
- blocks worker extraction if the number of `content_list_v2.json` table blocks differs from the number of HTML tables in `full.md`; finish the requested task and report the mismatch to the user instead of spawning a worker for that paper
- removes top-level parser byproducts so only `full.md`, `*_origin.pdf`, `content_list_v2.json`, and `images/` remain

Use `--dry-run` first when the supplied directory is ambiguous or when checking an already processed package. Stop and inspect warnings if table images are not ready, if table counts differ, or if the shortened target directory already exists.

For table replacement only, use:

```bash
python .codex/skills/cfst-orchestrator/scripts/replace_html_tables_with_images.py \
  '<rawdata-root>/[A1-1]' \
  --in-place \
  --overwrite \
  --strict-count
```

3. Prepare the batch workspace:

```bash
python .codex/skills/cfst-orchestrator/scripts/prepare_batch.py \
  --processed-root processed
```

4. Read `output/manifests/worker_jobs.json`. Process only papers whose `status` is `prepared`. Use `paper_pdf_relpath` and `worker_output_json_path` exactly as written; do not reconstruct them from `paper_id`.

5. Create one isolated worktree per prepared paper:

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

6. Spawn exactly one worker sub-agent per paper. Cap concurrency at 5. The worker owns only one paper, one worktree, and one temp JSON path.

7. Use this worker brief template:

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
- rawdata_dir: <rawdata-root>/[<paper_id>] after parent preprocessing, or the unique prepared rawdata directory whose basename is [<paper_id>]
- full_md_path: <rawdata_dir>/full.md
- images_dir: <rawdata_dir>/images
- content_list_path: <rawdata_dir>/content_list_v2.json

Authoritative files inside the worktree:
- .codex/skills/cfst-column-extractor/SKILL.md
- .codex/skills/cfst-column-extractor/references/extraction-rules.md
- .codex/skills/cfst-column-extractor/references/fc-basis-rules.md
- .codex/skills/cfst-column-extractor/references/section_shapes.jpg
- .codex/skills/cfst-column-extractor/references/cfst-extraction-schema.json
- .codex/skills/cfst-column-extractor/references/JSON_contract.md

Parent-owned constraints:
- Work only on this one paper.
- Do not use `.codex/skills/cfst-orchestrator/SKILL.md` as extraction policy.
- Use `full_md_path` as the default extraction source, open only referenced `images_dir` files as needed, use the PDF only as fallback/conflict resolver, and use `content_list_path` only for locating parsed/PDF blocks.
- Write exactly one JSON file on disk to `temp_json_host_path`.
- Write no secondary extraction artifacts.
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
      --strict-rounding
- If validation fails for schema, data, source-summary/note, or extraction-decision reasons documented in `.codex/skills/cfst-column-extractor/references/JSON_contract.md`, repair once and rerun the same validator command. If validation fails because of a rule not documented there, stop and report a documentation/validator mismatch.
- If the sandbox reports a path, mount, or startup failure, stop and return that failure to the parent.

Return exactly:
- paper_id
- temp_json path (`temp_json_workspace_path`)
- validation pass/fail
- failure reason if any
```

8. Immediately after launch, mark the paper `running`:

```bash
python .codex/skills/cfst-orchestrator/scripts/update_batch_state.py \
  --batch-state output/manifests/batch_state.json \
  --paper-id <paper_id> \
  --status running \
  --validated false \
  --published false \
  --clear-last-error
```

9. Monitor active workers with long waits. Do not interrupt a normally running worker just because a short poll timed out.

10. When a worker finishes:

- if it succeeded and the temp JSON exists, mark `ready_for_publication`
- if it failed for schema, data, source-summary/note, or extraction-decision reasons, retry once on a fresh worktree with the exact failure
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

11. Always remove each finished worktree:

```bash
python .codex/skills/cfst-orchestrator/scripts/git_worktree_isolation.py remove \
  --worktree-path '<worktree_path>' \
  --delete-branch
```

12. After all prepared papers finish, publish validated outputs with the child skill validator:

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

13. If repository policy requires checkpoints, run them only after publication:

```bash
python .codex/skills/cfst-orchestrator/scripts/checkpoint_output_commits.py \
  --processed-count <published_plus_failed_count> \
  --output-dir output/output
```

14. In the final report, distinguish:

- papers skipped before spawn because `worker_jobs.json.status != prepared`
- papers that failed after retry
- papers successfully published to `output/output/`

## Use These Scripts

- `scripts/bootstrap_git_repo.py`: initialize a repo and optional empty commit so worktree execution can start
- `scripts/prepare_rawdata_package.py`: shorten one rawdata paper directory, crop/replace table images, and remove parser byproducts before worker extraction
- `scripts/replace_html_tables_with_images.py`: crop caption-named table images from `content_list_v2.json` + `*_origin.pdf` and replace HTML table blocks in `full.md`
- `scripts/prepare_batch.py`: discover processed PDFs and write manifests/state for parent orchestration
- `scripts/git_worktree_isolation.py`: create and remove per-paper worktrees that contain the owned paper plus the child extraction skill
- `scripts/worker_sandbox.py`: run one worker command under `bwrap`, mounting the owned paper read-only, the child skill read-only, and the declared output directory read-write
- `scripts/update_batch_state.py`: update one paper entry in `batch_state.json`
- `scripts/publish_validated_output.py`: revalidate and publish temp outputs using the child skill validator
- `scripts/checkpoint_output_commits.py`: commit or push published outputs at fixed intervals when repository policy requires it
