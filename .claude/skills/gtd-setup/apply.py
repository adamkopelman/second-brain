#!/usr/bin/env python3
"""Idempotent scaffolder for the GTD second brain. Copies the bundled asset tree
into a target vault, creating only files that don't already exist. Standard library only."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

def apply(scaffold_root: Path, target: Path, force: bool = False) -> dict:
    scaffold_root = Path(scaffold_root)
    target = Path(target)
    created, skipped = [], []
    for src in sorted(scaffold_root.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(scaffold_root)
        dst = target / rel
        if dst.exists() and not force:
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        created.append(str(rel))
    return {"created": created, "skipped": skipped}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Scaffold or repair a GTD second-brain vault.")
    p.add_argument("target", nargs="?", default=".", help="vault root (default: current dir)")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)
    scaffold = Path(__file__).resolve().parent / "scaffold" / "vault"
    res = apply(scaffold, Path(args.target), force=args.force)
    for c in res["created"]:
        print(f"created {c}")
    for s in res["skipped"]:
        print(f"skipped {s}")
    print(f"\n{len(res['created'])} created, {len(res['skipped'])} skipped")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
