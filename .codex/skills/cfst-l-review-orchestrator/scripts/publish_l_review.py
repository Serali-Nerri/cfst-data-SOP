#!/usr/bin/env python3
"""Re-validate worker review outputs, publish them, and record publish logs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestrator_common import (
    PUBLISHED_STATUS,
    PUBLISH_FAILED_STATUS,
    READY_FOR_PUBLICATION_STATUS,
    atomic_write_json,
    read_json,
    validate_status,
    write_json,
)

DEFAULT_REVIEWER_SKILL_DIR = Path(".codex/skills/cfst-l-reviewer")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def apply_batch_state_update(
    batch_state_payload: dict[str, Any],
    paper_id: str,
    *,
    published: bool,
    validated: bool,
    status: str,
    last_error: str | None,
) -> None:
    validate_status(status)
    papers = batch_state_payload.get("papers", [])
    for paper in papers:
        if paper.get("paper_id") != paper_id:
            continue
        paper["published"] = published
        paper["validated"] = validated
        paper["status"] = status
        paper["last_error"] = last_error
        return
    raise ValueError(f"paper_id not found in batch state: {paper_id}")


def read_batch_state(batch_state_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = read_json(batch_state_path)
    if not isinstance(payload, dict):
        raise ValueError(f"batch state must contain a JSON object: {batch_state_path}")
    papers = payload.get("papers", [])
    if not isinstance(papers, list):
        raise ValueError(f"batch state papers must be a list: {batch_state_path}")
    result: dict[str, dict[str, Any]] = {}
    for paper in papers:
        paper_id = paper.get("paper_id") if isinstance(paper, dict) else None
        if isinstance(paper_id, str):
            status = paper.get("status")
            if isinstance(status, str):
                validate_status(status)
            result[paper_id] = paper
    return payload, result


def atomic_copy(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_name(f".{dest.name}.tmp-{os.getpid()}")
    try:
        shutil.copy2(source, tmp_path)
        os.replace(tmp_path, dest)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def revalidate(
    validator_script: Path,
    review_path: Path,
    csv_path: Path,
    recommended_csv_path: Path,
) -> tuple[bool, str]:
    result = subprocess.run(
        [
            sys.executable,
            str(validator_script),
            "--review-md",
            str(review_path),
            "--csv",
            str(csv_path),
            "--recommended-csv",
            str(recommended_csv_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, "validated"
    message = (result.stderr or result.stdout or "").strip().splitlines()
    return False, "; ".join(message) if message else f"validator exited {result.returncode}"


def publish_one(
    *,
    paper: dict[str, Any],
    validator_script: Path,
) -> tuple[bool, str, dict[str, Any]]:
    paper_id = paper["paper_id"]
    package = paper.get("package", {}) or {}
    csv_path_value = package.get("extracted_csv_path")
    if not isinstance(csv_path_value, str):
        return False, "manifest missing package.extracted_csv_path", {}
    csv_path = Path(csv_path_value)

    worker_review_path = Path(paper["worker_review_path"])
    worker_recommended_csv_path = Path(paper["worker_recommended_csv_path"])
    final_review_path = Path(paper["final_review_path"])
    final_recommended_csv_path = Path(paper["final_recommended_csv_path"])

    if not worker_review_path.is_file():
        return False, f"missing worker review.md: {worker_review_path}", {}
    if not csv_path.is_file():
        return False, f"missing input CSV: {csv_path}", {}

    ok, message = revalidate(
        validator_script,
        worker_review_path,
        csv_path,
        worker_recommended_csv_path,
    )
    if not ok:
        return False, message, {}

    atomic_copy(worker_review_path, final_review_path)
    if worker_recommended_csv_path.is_file():
        atomic_copy(worker_recommended_csv_path, final_recommended_csv_path)
        recommended_published = True
    else:
        if final_recommended_csv_path.exists():
            final_recommended_csv_path.unlink()
        recommended_published = False

    return True, "published", {
        "paper_id": paper_id,
        "review_path": str(final_review_path),
        "recommended_csv_path": str(final_recommended_csv_path) if recommended_published else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish validated L-review worker outputs.")
    parser.add_argument("--batch-manifest", type=Path, required=True, help="Path to l_review_batch_manifest.json.")
    parser.add_argument("--tmp-root", type=Path, required=True, help="Temp root containing worker outputs (unused unless paths are missing).")
    parser.add_argument("--output-dir", type=Path, required=True, help="Final output directory root (e.g. output/output/L-review).")
    parser.add_argument("--publish-log", type=Path, required=True, help="JSONL publish log path.")
    parser.add_argument(
        "--reviewer-skill-dir",
        type=Path,
        default=DEFAULT_REVIEWER_SKILL_DIR,
        help="Path to the child reviewer skill (for re-validation).",
    )
    parser.add_argument(
        "--batch-state",
        type=Path,
        default=None,
        help="Optional l_review_batch_state.json path to update as papers publish.",
    )
    parser.add_argument(
        "--paper-ids",
        nargs="*",
        default=None,
        help="Optional subset of paper_ids to publish.",
    )
    args = parser.parse_args()

    validator_script = (args.reviewer_skill_dir / "scripts" / "validate_review_output.py").resolve()
    if not validator_script.is_file():
        print(f"[FAIL] reviewer validator not found: {validator_script}")
        return 1

    manifest = read_json(args.batch_manifest)
    if not isinstance(manifest, dict):
        print(f"[FAIL] batch manifest must contain a JSON object: {args.batch_manifest}")
        return 1
    papers = manifest.get("papers", [])
    if not isinstance(papers, list):
        print(f"[FAIL] batch manifest papers must be a list: {args.batch_manifest}")
        return 1
    requested_ids = set(args.paper_ids or [])
    if requested_ids:
        available_ids = {paper["paper_id"] for paper in papers}
        missing_ids = sorted(requested_ids - available_ids)
        if missing_ids:
            print(f"[FAIL] Unknown paper_ids in --paper-ids: {', '.join(missing_ids)}")
            return 1
        papers = [paper for paper in papers if paper["paper_id"] in requested_ids]

    batch_state_payload: dict[str, Any] | None = None
    if args.batch_state:
        try:
            batch_state_payload, state_by_id = read_batch_state(args.batch_state)
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            return 1
        not_ready_ids = {
            paper.get("paper_id")
            for paper in papers
            if state_by_id.get(paper.get("paper_id"), {}).get("status") != READY_FOR_PUBLICATION_STATUS
        }
        if requested_ids and not_ready_ids:
            id_list = ", ".join(sorted(str(paper_id) for paper_id in not_ready_ids))
            print(f"[FAIL] Requested papers are not {READY_FOR_PUBLICATION_STATUS}: {id_list}")
            return 1
        before_count = len(papers)
        papers = [paper for paper in papers if paper.get("paper_id") not in not_ready_ids]
        skipped_count = before_count - len(papers)
        if skipped_count:
            print(f"[INFO] Skipped {skipped_count} papers not {READY_FOR_PUBLICATION_STATUS}.")

    publish_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requested_paper_ids": sorted(requested_ids) if requested_ids else None,
        "published": 0,
        "failed": 0,
        "items": [],
    }

    for paper in papers:
        paper_id = paper["paper_id"]
        ok, message, info = publish_one(paper=paper, validator_script=validator_script)
        log_item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paper_id": paper_id,
            "published": ok,
            "message": message,
            "info": info,
        }
        append_jsonl(args.publish_log, log_item)
        publish_summary["items"].append(log_item)
        if batch_state_payload is not None:
            try:
                apply_batch_state_update(
                    batch_state_payload=batch_state_payload,
                    paper_id=paper_id,
                    published=ok,
                    validated=ok,
                    status=PUBLISHED_STATUS if ok else PUBLISH_FAILED_STATUS,
                    last_error=None if ok else message,
                )
            except ValueError as exc:
                print(f"[FAIL] {paper_id}: {exc}")
                return 1
        if ok:
            publish_summary["published"] += 1
            print(f"[OK] {paper_id}: {info.get('review_path')}")
        else:
            publish_summary["failed"] += 1
            print(f"[FAIL] {paper_id}: {message}")

    if batch_state_payload is not None:
        atomic_write_json(args.batch_state, batch_state_payload)
    write_json(args.publish_log.with_suffix(".summary.json"), publish_summary)
    print(
        f"[INFO] Published={publish_summary['published']} Failed={publish_summary['failed']} "
        f"Log={args.publish_log}"
    )
    return 0 if publish_summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
