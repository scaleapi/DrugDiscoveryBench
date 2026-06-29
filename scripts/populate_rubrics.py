#!/usr/bin/env python3
"""Populate task rubrics + ground truth from the gated HuggingFace dataset.

The scoring rubrics and reference answers for every task are NOT stored in this
repo. They are released through a gated HuggingFace dataset so the benchmark can
be public without exposing answers to training corpora:

    https://huggingface.co/datasets/ScaleAI/DrugDiscoveryBench

Each task's ``tests/rubrics.json`` ships here with empty ``ground_truth`` /
``outcome_rubrics`` / ``process_rubrics`` fields. This script downloads the
dataset and fills those fields back in, in place, so the judge can grade trials.

Prerequisites
-------------
1. Request access to the dataset (one click) at the URL above and wait for the
   automatic approval e-mail.
2. Authenticate, either with a cached login or an env var / flag:

       huggingface-cli login          # interactive, cached
       export HF_TOKEN=hf_xxx          # or pass --token hf_xxx

Usage
-----
    python scripts/populate_rubrics.py            # populate all tasks
    python scripts/populate_rubrics.py --dry-run  # report only, write nothing

Idempotent: re-running simply re-writes the same content.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TASKS_DIR = REPO / "benchmark" / "tasks"
DEFAULT_HF_REPO = "ScaleAI/DrugDiscoveryBench"


def _rubric_item(c: dict) -> dict:
    """Reconstruct the on-disk rubric shape (justification/category may be absent in the dataset)."""
    return {
        "title": c.get("title", ""),
        "weight": c.get("weight", ""),
        "justification": c.get("justification", ""),
        "category": c.get("category", ""),
    }


def _load_dataset(hf_repo: str, token: str | None) -> dict[str, dict]:
    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError
    except ImportError:
        sys.exit("huggingface_hub is required: pip install huggingface_hub")
    try:
        path = hf_hub_download(repo_id=hf_repo, filename="tasks.jsonl",
                               repo_type="dataset", token=token)
    except GatedRepoError:
        sys.exit(
            f"Access to '{hf_repo}' has not been granted for this account.\n"
            f"Request access at https://huggingface.co/datasets/{hf_repo} and, once approved,\n"
            "authenticate with `huggingface-cli login` (or set HF_TOKEN / pass --token)."
        )
    except RepositoryNotFoundError:
        sys.exit(
            f"Could not find '{hf_repo}'. If it is gated/private, authenticate first "
            "(`huggingface-cli login`, or set HF_TOKEN / pass --token)."
        )
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return {r["task_id"]: r for r in rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hf-repo", default=DEFAULT_HF_REPO, help=f"HF dataset id (default: {DEFAULT_HF_REPO})")
    ap.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR,
                    help=f"tasks directory (default: {DEFAULT_TASKS_DIR})")
    ap.add_argument("--token", default=os.environ.get("HF_TOKEN"),
                    help="HF access token (default: $HF_TOKEN or cached login)")
    ap.add_argument("--dry-run", action="store_true", help="report only; do not write files")
    args = ap.parse_args()

    data = _load_dataset(args.hf_repo, args.token)
    print(f"Loaded {len(data)} task records from {args.hf_repo}")

    task_dirs = sorted(p for p in args.tasks_dir.iterdir()
                       if p.is_dir() and (p / "tests" / "rubrics.json").is_file())
    if not task_dirs:
        sys.exit(f"No task rubrics.json files found under {args.tasks_dir}")

    populated, missing_in_hf = 0, []
    repo_ids = set()
    for d in task_dirs:
        tid = d.name
        repo_ids.add(tid)
        row = data.get(tid)
        if row is None:
            missing_in_hf.append(tid)
            continue
        rp = d / "tests" / "rubrics.json"
        bundle = json.loads(rp.read_text())
        bundle["ground_truth"] = row.get("ground_truth", "")
        bundle["outcome_rubrics"] = [_rubric_item(c) for c in row.get("outcome_rubrics", [])]
        bundle["process_rubrics"] = [_rubric_item(c) for c in row.get("process_rubrics", [])]
        if not args.dry_run:
            rp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
        populated += 1

    print(f"{'Would populate' if args.dry_run else 'Populated'} {populated} task(s)")
    if missing_in_hf:
        print(f"WARNING: {len(missing_in_hf)} task(s) in the repo are not in the dataset "
              f"(left untouched): {', '.join(missing_in_hf)}", file=sys.stderr)
    extra = sorted(set(data) - repo_ids)
    if extra:
        print(f"NOTE: {len(extra)} dataset task(s) have no matching directory here: {', '.join(extra)}")
    if args.dry_run:
        print("Dry run — no files written.")


if __name__ == "__main__":
    main()
