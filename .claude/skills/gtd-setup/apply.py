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

def apply_plugin_data(plugin_data_root: Path, target: Path, force: bool = False) -> dict:
    """Install the vault's preset plugin settings (scaffold/plugin-data/<id>/data.json) into
    .obsidian/plugins/<id>/. The plugins themselves are optional git submodules (or installed from
    Obsidian's community store), so a preset goes only into a plugin that is actually installed
    (its manifest.json exists), and never over settings the user already has unless force."""
    plugin_data_root = Path(plugin_data_root)
    target = Path(target)
    created, skipped, missing = [], [], []
    for src in sorted(plugin_data_root.glob("*/data.json")):
        plugin_id = src.parent.name
        plugin_dir = target / ".obsidian" / "plugins" / plugin_id
        rel = f".obsidian/plugins/{plugin_id}/data.json"
        if not (plugin_dir / "manifest.json").is_file():
            missing.append(plugin_id)
            continue
        dst = plugin_dir / "data.json"
        if dst.exists() and not force:
            skipped.append(rel)
            continue
        shutil.copyfile(src, dst)
        created.append(rel)
    return {"created": created, "skipped": skipped, "missing": missing}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Scaffold or repair a GTD second-brain vault.")
    p.add_argument("target", nargs="?", default=".", help="vault root (default: current dir)")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)
    here = Path(__file__).resolve().parent
    res = apply(here / "scaffold" / "vault", Path(args.target), force=args.force)
    plugins = apply_plugin_data(here / "scaffold" / "plugin-data", Path(args.target), force=args.force)
    for c in res["created"] + plugins["created"]:
        print(f"created {c}")
    for s in res["skipped"] + plugins["skipped"]:
        print(f"skipped {s}")
    for m in plugins["missing"]:
        print(f"plugin not installed, preset not applied: {m} "
              "(git submodule update --init, or install it from Obsidian, then re-run)")
    n_created = len(res["created"]) + len(plugins["created"])
    n_skipped = len(res["skipped"]) + len(plugins["skipped"])
    print(f"\n{n_created} created, {n_skipped} skipped")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
