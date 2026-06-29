#!/usr/bin/env python3
"""Switch every task's trial image to a given tier (lightweight | core | full).

Each task pins the image in two places — ``docker_image`` in its ``task.toml`` and
the ``FROM`` line in its ``environment/Dockerfile``. Tasks ship pinned to the
``lightweight`` tier (the eval data-lake files baked in; ``query_*`` DB clients hit
live APIs). The ``core`` and ``full`` tiers additionally bake the ``query_*``
databases into the image for offline, deterministic runs (~74% / ~99.7% of
``query_*`` calls served locally). This rewrites the tier tag across every task and
the ``_template`` in place.

    ghcr.io/scaleapi/drugdiscoverybench:1.0.0-lightweight   (default)
    ghcr.io/scaleapi/drugdiscoverybench:1.0.0-core
    ghcr.io/scaleapi/drugdiscoverybench:1.0.0-full

Usage
-----
    python scripts/set_image_tier.py core          # pin all tasks to 1.0.0-core
    python scripts/set_image_tier.py lightweight   # back to the default
    python scripts/set_image_tier.py full --dry-run

Idempotent: re-running with the same tier writes nothing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_BENCH = REPO / "benchmark"
DEFAULT_IMAGE = "ghcr.io/scaleapi/drugdiscoverybench"
DEFAULT_VERSION = "1.0.0"
TIERS = ("lightweight", "core", "full")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("tier", choices=TIERS, help="image tier to pin across all tasks")
    ap.add_argument("--image", default=DEFAULT_IMAGE, help=f"image repo (default: {DEFAULT_IMAGE})")
    ap.add_argument("--version", default=DEFAULT_VERSION, help=f"version tag prefix (default: {DEFAULT_VERSION})")
    ap.add_argument("--bench-dir", type=Path, default=DEFAULT_BENCH, help=f"benchmark dir (default: {DEFAULT_BENCH})")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    # match the image ref carrying ANY of the known tier tags, so the switch works
    # regardless of which tier is currently pinned.
    pat = re.compile(
        re.escape(args.image) + r":" + re.escape(args.version) + r"-(?:" + "|".join(TIERS) + r")"
    )
    target = f"{args.image}:{args.version}-{args.tier}"

    files = sorted(
        list(args.bench_dir.glob("tasks/*/task.toml"))
        + list(args.bench_dir.glob("tasks/*/environment/Dockerfile"))
        + list(args.bench_dir.glob("_template/task.toml"))
        + list(args.bench_dir.glob("_template/environment/Dockerfile"))
    )
    if not files:
        sys.exit(f"No task.toml / Dockerfile found under {args.bench_dir}")

    refs = 0
    modified = 0
    for f in files:
        text = f.read_text()
        new, n = pat.subn(target, text)
        if n:
            refs += n
            if new != text:
                modified += 1
                if not args.dry_run:
                    f.write_text(new)

    verb = "Would pin" if args.dry_run else "Pinned"
    print(f"{verb} {refs} image ref(s) across {len(files)} file(s) -> {target}")
    print(f"files {'to change' if args.dry_run else 'changed'}: {modified}")
    if refs == 0:
        print(f"WARNING: found no {args.image}:{args.version}-* refs to rewrite.", file=sys.stderr)
    if args.dry_run:
        print("Dry run — no files written.")


if __name__ == "__main__":
    main()
