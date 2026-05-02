#!/usr/bin/env python3
"""Update one paper entry inside batch_state.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator_common import atomic_write_json, read_json, validate_status


def parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {raw}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update one paper entry in batch_state.json.")
    parser.add_argument("--batch-state", type=Path, required=True, help="Path to batch_state.json.")
    parser.add_argument("--paper-id", required=True, help="Paper id to update, e.g. A2-21.")
    parser.add_argument("--status", default=None, help="New status string.")
    parser.add_argument("--retry-count", type=int, default=None, help="Set retry_count exactly.")
    parser.add_argument(
        "--increment-retry-count",
        action="store_true",
        help="Increment retry_count by 1.",
    )
    parser.add_argument("--validated", type=parse_bool, default=None, help="Set validated true/false.")
    parser.add_argument("--published", type=parse_bool, default=None, help="Set published true/false.")
    parser.add_argument("--last-error", default=None, help="Set last_error to this string.")
    parser.add_argument(
        "--clear-last-error",
        action="store_true",
        help="Clear last_error to null.",
    )
    args = parser.parse_args()

    payload = read_json(args.batch_state)
    if not isinstance(payload, dict):
        print(f"[FAIL] batch state must contain a JSON object: {args.batch_state}")
        return 1
    papers = payload.get("papers", [])
    if not isinstance(papers, list):
        print(f"[FAIL] batch state papers must be a list: {args.batch_state}")
        return 1
    entry = next(
        (item for item in papers if isinstance(item, dict) and item.get("paper_id") == args.paper_id),
        None,
    )
    if entry is None:
        print(f"[FAIL] paper_id not found in batch state: {args.paper_id}")
        return 1

    if args.status is not None:
        try:
            validate_status(args.status)
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            return 1
        entry["status"] = args.status
    if args.retry_count is not None:
        if args.retry_count < 0:
            print("[FAIL] --retry-count must be >= 0.")
            return 1
        entry["retry_count"] = args.retry_count
    if args.increment_retry_count:
        entry["retry_count"] = int(entry.get("retry_count", 0)) + 1
    if args.validated is not None:
        entry["validated"] = args.validated
    if args.published is not None:
        entry["published"] = args.published
    if args.last_error is not None:
        entry["last_error"] = args.last_error
    if args.clear_last_error:
        entry["last_error"] = None

    atomic_write_json(args.batch_state, payload)
    print(json.dumps(entry, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
