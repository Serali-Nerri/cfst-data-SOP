#!/usr/bin/env python3
"""Build one L-review worker workspace, job spec, and worker brief."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import time
from pathlib import Path
from typing import Any

from orchestrator_common import (
    inspect_l_review_package,
    is_under,
    normalize_paper_id,
    read_json,
    write_json,
)


DEFAULT_REVIEWER_SKILL_DIR = Path(".codex/skills/cfst-l-reviewer")
DEFAULT_ORCHESTRATOR_SKILL_DIR = Path(".codex/skills/cfst-l-review-orchestrator")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sort_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-_.") or "paper"


def copy_tree(src: Path, dst: Path, overwrite: bool) -> None:
    if not src.exists():
        raise FileNotFoundError(f"source path not found: {src}")
    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"destination already exists: {dst}")
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def find_job(worker_jobs: list[dict[str, Any]], paper_id: str) -> dict[str, Any]:
    for job in worker_jobs:
        if job.get("paper_id") == paper_id:
            return job
    raise KeyError(f"paper_id not found in worker_jobs: {paper_id}")


def required_path(job: dict[str, Any], key: str) -> Path:
    value = job.get(key)
    if not value:
        raise ValueError(f"worker job missing {key}")
    path = Path(value).resolve()
    if not path.exists():
        raise ValueError(f"worker job {key} does not exist: {path}")
    return path


def command_string(args: list[str]) -> str:
    return shlex.join(args)


def build_brief(spec: dict[str, Any]) -> str:
    package = spec["package"]
    output = spec["output"]
    workspace = spec["workspace"]
    commands = spec["commands"]
    return f"""Own exactly one CFST paper L review.
Use the $cfst-l-reviewer skill for review policy and review.md authoring rules.

Inputs:
- paper_id: {spec["paper_id"]}
- package_dir: {package["workspace_dir"]}
- owned_pdf_path: {package["owned_pdf_path"]}
- extracted_csv_path: {package["extracted_csv_path"]}
- output_review_path: {output["review_host_path"]}
- recommended_csv_path: {output["recommended_csv_host_path"]}
- workspace_tmp_dir: {workspace["tmp_dir"]}

Package contract:
- Read `full.md`, `images/`, `content_list_v2.json`, and `<paper_id>.csv` from `package_dir`.
- Use `owned_pdf_path` only as the package-owned PDF fallback or conflict resolver.
- Use only these caller-provided paths and fixed package members; if unusable, return `input_contract_failure`.

Commands:
- validation_command:
```bash
{commands["validation_command"]}
```

Execution constraints:
- Write `review.md` to `output_review_path`.
- Write `recommended_csv_path` only if any specimen verdict is `CHANGE` (same header as the original CSV, only the CHANGE rows with updated `L`).
- Run `validation_command` exactly as given after writing the review.
- Use `workspace_tmp_dir` for intermediate scratch files.
- For each specimen verdict, derive the judgment step by step from the available evidence before writing the review.
- Report undocumented validator rules as `documentation_validator_mismatch`.

Return exactly:
- paper_id
- output_review_path
- status: success | input_contract_failure | review_failure | validation_failure | documentation_validator_mismatch
- validation pass/fail
- failure reason if any
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one CFST L-review worker job spec and worker brief.")
    parser.add_argument("--worker-jobs", type=Path, default=Path("output/manifests/l_review_worker_jobs.json"))
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--worker-spaces-root", type=Path, default=Path("tmp/cfst-l-review-worker-spaces"))
    parser.add_argument("--reviewer-skill-dir", type=Path, default=DEFAULT_REVIEWER_SKILL_DIR)
    parser.add_argument("--orchestrator-skill-dir", type=Path, default=DEFAULT_ORCHESTRATOR_SKILL_DIR)
    parser.add_argument("--force", action="store_true", help="Overwrite destination paths if they already exist.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    worker_jobs_path = (
        repo_root / args.worker_jobs
        if not args.worker_jobs.is_absolute()
        else args.worker_jobs
    ).resolve()
    reviewer_skill_src = (
        repo_root / args.reviewer_skill_dir
        if not args.reviewer_skill_dir.is_absolute()
        else args.reviewer_skill_dir
    ).resolve()
    orchestrator_skill_dir = (
        args.orchestrator_skill_dir
        if args.orchestrator_skill_dir.is_absolute()
        else repo_root / args.orchestrator_skill_dir
    ).resolve()

    if not repo_root.is_dir():
        print(f"[FAIL] repo root not found: {repo_root}")
        return 1
    if not worker_jobs_path.is_file():
        print(f"[FAIL] worker jobs file not found: {worker_jobs_path}")
        return 1
    if not reviewer_skill_src.is_dir():
        print(f"[FAIL] reviewer skill dir not found: {reviewer_skill_src}")
        return 1
    if not orchestrator_skill_dir.is_dir():
        print(f"[FAIL] orchestrator skill dir not found: {orchestrator_skill_dir}")
        return 1

    try:
        worker_jobs = read_json(worker_jobs_path)
        if not isinstance(worker_jobs, list):
            raise ValueError("worker_jobs JSON must contain a list")
        paper_id = normalize_paper_id(args.paper_id)
        job = find_job(worker_jobs, paper_id)
        if job.get("status") != "prepared":
            raise ValueError(f"worker job status is not prepared: {job.get('status')}")

        source_package_dir = required_path(job, "package_dir")
        package_info = inspect_l_review_package(source_package_dir, paper_id)
        if not package_info["ready"]:
            raise ValueError(
                "source package is not prepared: " + ", ".join(package_info["issues"])
            )
        source_pdf = Path(package_info["owned_pdf_path"])

        raw_review_path = Path(job["worker_review_path"])
        review_host = (
            raw_review_path if raw_review_path.is_absolute() else repo_root / raw_review_path
        ).resolve()
        raw_recommended_csv = Path(job["worker_recommended_csv_path"])
        recommended_csv_host = (
            raw_recommended_csv if raw_recommended_csv.is_absolute() else repo_root / raw_recommended_csv
        ).resolve()
        review_host.parent.mkdir(parents=True, exist_ok=True)

        worker_spaces_root = (
            repo_root / args.worker_spaces_root
            if not args.worker_spaces_root.is_absolute()
            else args.worker_spaces_root
        ).resolve()
        if is_under(source_package_dir, worker_spaces_root) or is_under(worker_spaces_root, source_package_dir):
            raise ValueError(
                f"worker spaces root must not overlap source package: {worker_spaces_root} / {source_package_dir}"
            )
        if is_under(reviewer_skill_src, worker_spaces_root) or is_under(worker_spaces_root, reviewer_skill_src):
            raise ValueError(
                f"worker spaces root must not overlap reviewer skill: {worker_spaces_root} / {reviewer_skill_src}"
            )

        stamp = time.strftime("%Y%m%d-%H%M%S")
        workspace_path = (
            worker_spaces_root / f"{sort_slug(paper_id)}-{stamp}-{os.getpid()}"
        ).resolve()
        partial_workspace_path = workspace_path.with_name(f"{workspace_path.name}.partial")
        pending_root_name = source_package_dir.parent.name or "Pending"
        package_rel = f"{pending_root_name}/[{paper_id}]"
        package_dst = workspace_path / package_rel
        skill_rel = ".codex/skills/cfst-l-reviewer"
        tmp_rel = "tmp"
        tmp_dst = workspace_path / tmp_rel
        partial_package_dst = partial_workspace_path / package_rel
        partial_skill_dst = partial_workspace_path / skill_rel
        partial_tmp_dst = partial_workspace_path / tmp_rel

        if workspace_path.exists():
            if not args.force:
                raise FileExistsError(f"workspace already exists: {workspace_path}")
            remove_path(workspace_path)
        if partial_workspace_path.exists():
            if not args.force:
                raise FileExistsError(f"partial workspace already exists: {partial_workspace_path}")
            remove_path(partial_workspace_path)

        copy_tree(source_package_dir, partial_package_dst, args.force)
        copy_tree(reviewer_skill_src, partial_skill_dst, args.force)
        partial_tmp_dst.mkdir(parents=True, exist_ok=True)

        copied_package_info = inspect_l_review_package(partial_package_dst, paper_id)
        if not copied_package_info["ready"]:
            raise ValueError(
                "copied workspace package is not prepared: "
                + ", ".join(copied_package_info["issues"])
            )
        partial_workspace_path.rename(workspace_path)

        owned_pdf_dst = package_dst / source_pdf.name
        if not owned_pdf_dst.is_file():
            matches = sorted(package_dst.glob("*_origin.pdf"))
            if len(matches) != 1:
                raise ValueError(f"workspace package must contain exactly one *_origin.pdf: {package_dst}")
            owned_pdf_dst = matches[0]
        extracted_csv_dst = package_dst / f"{paper_id}.csv"
        if not extracted_csv_dst.is_file():
            raise ValueError(f"workspace package missing extracted CSV: {extracted_csv_dst}")

        validator_script = (workspace_path / skill_rel / "scripts" / "validate_review_output.py").resolve()
        validation_command = command_string(
            [
                "python3",
                str(validator_script),
                "--review-md",
                str(review_host),
                "--csv",
                str(extracted_csv_dst),
                "--recommended-csv",
                str(recommended_csv_host),
            ]
        )

        spec_path = review_host.parent / "l_review_worker_job_spec.json"
        brief_path = review_host.parent / "worker_brief.md"
        spec = {
            "schema_version": "cfst-l-review-worker-job-v1",
            "paper_id": paper_id,
            "source_job": {
                "worker_jobs_path": str(worker_jobs_path),
                "package_dir": str(source_package_dir),
            },
            "workspace": {
                "path": str(workspace_path),
                "package_relpath": package_rel,
                "skill_relpath": skill_rel,
                "tmp_dir": str(tmp_dst),
            },
            "package": {
                "source_dir": str(source_package_dir),
                "workspace_dir": str(package_dst),
                "full_md_path": str(package_dst / "full.md"),
                "images_dir": str(package_dst / "images"),
                "content_list_path": str(package_dst / "content_list_v2.json"),
                "owned_pdf_path": str(owned_pdf_dst),
                "extracted_csv_path": str(extracted_csv_dst),
            },
            "output": {
                "review_host_path": str(review_host),
                "recommended_csv_host_path": str(recommended_csv_host),
                "host_output_dir": str(review_host.parent),
                "final_review_path": job["final_review_path"],
                "final_recommended_csv_path": job["final_recommended_csv_path"],
            },
            "commands": {
                "validation_command": validation_command,
            },
            "artifacts": {
                "job_spec_path": str(spec_path),
                "worker_brief_path": str(brief_path),
            },
        }
        write_json(spec_path, spec)
        write_text(brief_path, build_brief(spec))
    except (FileExistsError, FileNotFoundError, KeyError, ValueError) as exc:
        for path_name in ("partial_workspace_path", "workspace_path", "spec_path", "brief_path"):
            path = locals().get(path_name)
            if isinstance(path, Path):
                remove_path(path)
        print(f"[FAIL] {exc}")
        return 1

    print(
        json.dumps(
            {
                "paper_id": paper_id,
                "worker_job_spec_path": str(spec_path),
                "worker_brief_path": str(brief_path),
                "workspace_path": str(workspace_path),
                "output_review_path": str(review_host),
                "recommended_csv_path": str(recommended_csv_host),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
