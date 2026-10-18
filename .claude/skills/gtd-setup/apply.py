#!/usr/bin/env python3
"""Idempotent scaffolder for the GTD second brain. Copies the bundled asset tree
into a target vault, creating only files that don't already exist, applies the plugin presets, and
(on Windows) downloads the Outlook MCP server binary. Standard library only."""
from __future__ import annotations
import argparse
import hashlib
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

# outlook-mcp-rs is not committed; it is downloaded from the upstream GitHub release. Keep these in
# sync with vendor/outlook-mcp-rs/download-outlook-mcp-rs.ps1 and .sh (a test checks).
OUTLOOK_MCP_VERSION = "v0.3.0"
OUTLOOK_MCP_URL = ("https://github.com/adamkopelman/outlook-mcp-rs/releases/download/"
                   f"{OUTLOOK_MCP_VERSION}/outlook-mcp-rs.exe")
OUTLOOK_MCP_SHA256 = "b033325029562cac858551052ce6870010ecf8c9325206cf0233f45212619048"
OUTLOOK_MCP_REL = "vendor/outlook-mcp-rs/outlook-mcp-rs.exe"

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

def ensure_outlook_mcp(target: Path, platform: str | None = None, urlopen=None,
                       url: str = OUTLOOK_MCP_URL, sha256: str = OUTLOOK_MCP_SHA256) -> dict:
    """Download outlook-mcp-rs.exe from its GitHub release into vendor/outlook-mcp-rs/ and verify
    its SHA-256. Windows only (it drives the Outlook desktop app). An existing exe is left alone —
    it may be the user's own build. Returns {"status": present|downloaded|skipped|failed, "path",
    "error"}; a failure never leaves a partial file behind."""
    dest = Path(target) / OUTLOOK_MCP_REL
    platform = platform or sys.platform
    urlopen = urlopen or urllib.request.urlopen
    if dest.is_file():
        return {"status": "present", "path": dest, "error": None}
    if not platform.startswith("win"):
        return {"status": "skipped", "path": dest, "error": None}
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    try:
        with urlopen(url, timeout=60) as response, open(part, "wb") as out:
            for chunk in iter(lambda: response.read(1 << 16), b""):
                digest.update(chunk)
                out.write(chunk)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        part.unlink(missing_ok=True)
        reason = getattr(e, "reason", e)
        return {"status": "failed", "path": dest,
                "error": f"could not download {url} ({reason}) - are you offline? Nothing was "
                         "installed; re-run setup when connected, or run "
                         "vendor/outlook-mcp-rs/download-outlook-mcp-rs.ps1"}
    if digest.hexdigest() != sha256:
        part.unlink(missing_ok=True)
        return {"status": "failed", "path": dest,
                "error": f"checksum mismatch for {url}: expected {sha256}, got {digest.hexdigest()}; "
                         "nothing was installed"}
    part.replace(dest)
    return {"status": "downloaded", "path": dest, "error": None}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Scaffold or repair a GTD second-brain vault.")
    p.add_argument("target", nargs="?", default=".", help="vault root (default: current dir)")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    p.add_argument("--no-outlook-mcp", action="store_true",
                   help="don't download the Outlook MCP server binary (Windows)")
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
    rc = 0
    if not args.no_outlook_mcp:
        mcp = ensure_outlook_mcp(Path(args.target))
        exe = mcp["path"].resolve()
        if mcp["status"] == "downloaded":
            n_created += 1
            print(f"created {OUTLOOK_MCP_REL} (outlook-mcp-rs {OUTLOOK_MCP_VERSION} from GitHub "
                  "releases, sha256 verified)")
        elif mcp["status"] == "present":
            n_skipped += 1
            print(f"skipped {OUTLOOK_MCP_REL}")
        elif mcp["status"] == "skipped":
            print("outlook-mcp-rs: Windows-only binary, not downloaded")
        else:
            rc = 1
            print(f"error: outlook-mcp-rs: {mcp['error']}", file=sys.stderr)
        if mcp["status"] in ("downloaded", "present") and os.environ.get("OUTLOOK_MCP_BIN") != str(exe):
            print(f'outlook-mcp-rs: to let .mcp.json / opencode.json launch it, run: '
                  f'setx OUTLOOK_MCP_BIN "{exe}"')
    print(f"\n{n_created} created, {n_skipped} skipped")
    return rc

if __name__ == "__main__":
    raise SystemExit(main())
