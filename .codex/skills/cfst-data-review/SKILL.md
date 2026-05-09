---
name: cfst-data-review
description: "Use only when explicitly specified by the user; orchestrates CFST Pending/output preparation, per-paper CSV export, and fixed gpt-5.5 xhigh subagent review records."
---

# CFST Data Review

## Role

Act as the orchestrator. Prepare inputs, plan review jobs, launch subagents, track retries, and verify review artifacts. Do not perform the substantive single-paper data review yourself; delegate that work to subagents.

Users provide a `Pending` root and an `output` root. Paper IDs are unbracketed values such as `A1-72`; their Pending directories are bracketed, such as `Pending/[A1-72]`.

## Bundled References

This skill bundles the table-header reference and unified multi-section diagram under `references/`.

At the start of each workflow, prepare these files into the workspace root `tmp/`:

```bash
python .codex/skills/cfst-data-review/scripts/prepare_reference_tmp.py \
  --workspace-root .
```

Use the resulting workspace `tmp/` path as `{reference_dir}` in subagent prompts.

## Workflow

1. Resolve inputs:
   - `pending_root`: user-provided Pending directory.
   - `output_root`: user-provided output directory. If it contains `output/`, JSON files are read from `output_root/output`; otherwise from `output_root`.
   - `paper_ids`: user-specified IDs, or every JSON stem found under the output JSON directory.

2. Prepare numbered Pending folders before CSV export. This creates `tmp/` in each numbered folder and removes first-level non-PDF artifacts while preserving `tmp/`:

```bash
python .codex/skills/cfst-data-review/scripts/prepare_pending_dirs.py \
  --pending-root Pending \
  --delete-all-non-pdf
```

Use `--dry-run` first if the Pending root is ambiguous or may contain work that must be preserved.

3. Export each JSON to its corresponding Pending CSV:

```bash
python .codex/skills/cfst-data-review/scripts/export_jsons_to_pending_csv.py \
  --pending-root Pending \
  --output-root output
```

The export writes `Pending/[paper_id]/paper_id.csv` and uses the same columns and inheritance semantics as the CFST orchestrator CSV export.

4. Plan review jobs. For each paper, verify:
   - `Pending/[paper_id]/` exists.
   - exactly one `*_origin.pdf` exists.
   - `Pending/[paper_id]/paper_id.csv` exists.
   - `Pending/[paper_id]/tmp/` exists.

5. Launch one subagent per paper review. Cap concurrency at 5. Always use:
   - `fork_context: false`
   - `model: gpt-5.5`
   - `reasoning_effort: xhigh`

6. Retry policy: for the same paper, retry at most once. Retry only if the subagent errors, exits without creating the review file, or reports a terminal failure. Do not start a third attempt for the same paper; report it as failed.

7. After each subagent completes, verify `Pending/[paper_id]/paper_id_review.md` exists. Read only enough to summarize the outcome; do not redo the review.

## Subagent Prompt

Use this prompt template. Substitute paths exactly for the current workspace and paper.

```text
你是 CFST 研究方向的专家，请你带着审视的态度，仔细核对，这份 PDF 文献中提取出来的 CSV 表格数据是否正确，务必确保有理
  有据。

  工作区根目录：{workspace_root}
  审查对象：{paper_id}
  论文目录：{pending_root}/[{paper_id}]
  原始 PDF：{pending_root}/[{paper_id}] 下唯一的 *_origin.pdf
  待审查 CSV：{pending_root}/[{paper_id}]/{paper_id}.csv
  表头说明与多截面统一的示意图存放在：{reference_dir}
  临时文件存放到：{pending_root}/[{paper_id}]/tmp
  最终审查记录写入：{pending_root}/[{paper_id}]/{paper_id}_review.md
```

## Reporting

Report:

- Prepared Pending directory count.
- CSV files exported and any export failures.
- Review jobs launched, completed, retried, and failed.
- Review record paths generated.
- Any paper skipped because required inputs were missing.
