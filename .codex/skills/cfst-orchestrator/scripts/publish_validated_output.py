#!/usr/bin/env python3
"""Validate worker outputs, publish them to final output, and record publish logs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

from orchestrator_common import (
    PUBLISHED_STATUS,
    PUBLISH_FAILED_STATUS,
    READY_FOR_PUBLICATION_STATUS,
    atomic_write_json,
    read_json,
    validate_status,
    write_json,
)

DEFAULT_EXTRACTOR_SKILL_DIR = Path(".codex/skills/cfst-column-extractor")

ValidatePayload = Callable[[Any, bool | None, bool, int | None], tuple[list[str], list[str], int]]


def load_validate_payload(extractor_skill_dir: Path) -> ValidatePayload:
    validator_path = extractor_skill_dir / "scripts" / "validate_single_output.py"
    if not validator_path.is_file():
        raise FileNotFoundError(f"validator not found: {validator_path}")

    spec = importlib.util.spec_from_file_location("cfst_child_validate_single_output", validator_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"failed to load validator module: {validator_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    validate_payload = getattr(module, "validate_payload", None)
    if not callable(validate_payload):
        raise AttributeError(f"validate_payload not found in {validator_path}")
    return cast(ValidatePayload, validate_payload)


def payload_is_valid(payload: Any) -> bool | None:
    if not isinstance(payload, dict):
        return None
    paper = payload.get("paper")
    if not isinstance(paper, dict):
        return None
    validity = paper.get("validity")
    if not isinstance(validity, dict):
        return None
    value = validity.get("is_valid")
    return value if isinstance(value, bool) else None


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


def manifest_path(paper: dict[str, Any], key: str, fallback: Path) -> Path:
    value = paper.get(key)
    if isinstance(value, str) and value:
        return Path(value)
    return fallback


def atomic_copy(source_json: Path, dest_json: Path) -> None:
    dest_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_json.with_name(f".{dest_json.name}.tmp-{os.getpid()}")
    try:
        shutil.copy2(source_json, tmp_path)
        os.replace(tmp_path, dest_json)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def publish_one(
    source_json: Path,
    dest_json: Path,
    strict_rounding: bool,
    expect_count: int | None,
    validate_payload: ValidatePayload,
) -> tuple[bool, str]:
    if not source_json.exists():
        return False, f"missing worker output: {source_json}"

    payload = read_json(source_json)
    errors, warnings, _ = validate_payload(
        payload,
        payload_is_valid(payload),
        strict_rounding,
        expect_count,
    )
    if warnings:
        for warning in warnings:
            print(f"[WARN] {source_json.name}: {warning}")
    if errors:
        return False, "; ".join(errors)

    atomic_copy(source_json, dest_json)
    return True, "published"


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish validated worker outputs.")
    parser.add_argument("--batch-manifest", type=Path, required=True, help="Path to batch_manifest.json.")
    parser.add_argument("--tmp-root", type=Path, required=True, help="Temp root containing worker JSON outputs.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Final output directory.")
    parser.add_argument("--publish-log", type=Path, required=True, help="JSONL publish log path.")
    parser.add_argument(
        "--extractor-skill-dir",
        type=Path,
        default=DEFAULT_EXTRACTOR_SKILL_DIR,
        help="Path to the child extractor skill used to validate worker outputs.",
    )
    parser.add_argument(
        "--batch-state",
        type=Path,
        default=None,
        help="Optional batch_state.json path to update as papers publish.",
    )
    parser.add_argument(
        "--paper-ids",
        nargs="*",
        default=None,
        help="Optional subset of paper_ids to publish. Defaults to all papers in the batch manifest.",
    )
    parser.add_argument(
        "--strict-rounding",
        action="store_true",
        help="Fail publication when numeric rounding is not 0.001.",
    )
    args = parser.parse_args()

    try:
        validate_payload = load_validate_payload(args.extractor_skill_dir.resolve())
    except (AttributeError, FileNotFoundError, ImportError) as exc:
        print(f"[FAIL] {exc}")
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
        before_count = len(papers)
        not_ready = [
            paper
            for paper in papers
            if state_by_id.get(paper.get("paper_id"), {}).get("status") != READY_FOR_PUBLICATION_STATUS
        ]
        not_ready_ids = {paper.get("paper_id") for paper in not_ready}
        if requested_ids and not_ready:
            id_list = ", ".join(sorted(str(paper_id) for paper_id in not_ready_ids))
            print(f"[FAIL] Requested papers are not {READY_FOR_PUBLICATION_STATUS}: {id_list}")
            return 1
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
        expect_count = paper.get("expected_specimen_count")
        source_json = manifest_path(
            paper,
            "worker_output_json_path",
            args.tmp_root / paper_id / f"{paper_id}.json",
        )
        dest_json = manifest_path(
            paper,
            "final_output_json_path",
            args.output_dir / f"{paper_id}.json",
        )
        overwritten = dest_json.exists()
        ok, message = publish_one(
            source_json=source_json,
            dest_json=dest_json,
            strict_rounding=args.strict_rounding,
            expect_count=expect_count,
            validate_payload=validate_payload,
        )
        log_item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paper_id": paper_id,
            "source_path": str(source_json),
            "destination_path": str(dest_json),
            "overwritten": overwritten,
            "published": ok,
            "message": message,
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
            print(f"[OK] {paper_id}: {dest_json}")
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
