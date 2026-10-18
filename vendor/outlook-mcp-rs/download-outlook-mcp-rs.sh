#!/usr/bin/env sh
# Downloads outlook-mcp-rs.exe (the Outlook MCP server, a Windows binary) from the GitHub releases of
# https://github.com/adamkopelman/outlook-mcp-rs into this folder and verifies its SHA-256.
# Safe to re-run: an existing outlook-mcp-rs.exe is left alone (it may be your own build) unless --force.
#
#   sh vendor/outlook-mcp-rs/download-outlook-mcp-rs.sh [--force]      (Git Bash / WSL)
#
# Keep the version and hash in sync with download-outlook-mcp-rs.ps1 and
# .claude/skills/gtd-setup/apply.py.
set -eu

VERSION="v0.3.0"
URL="https://github.com/adamkopelman/outlook-mcp-rs/releases/download/$VERSION/outlook-mcp-rs.exe"
SHA256="b033325029562cac858551052ce6870010ecf8c9325206cf0233f45212619048"
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$DIR/outlook-mcp-rs.exe"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

if [ -f "$DEST" ] && [ "${1:-}" != "--force" ]; then
  echo "OK: $DEST is already present (left as is; --force downloads $VERSION over it)."
else
  echo "Downloading outlook-mcp-rs $VERSION from $URL ..."
  if ! curl -L --fail --retry 3 -o "$DEST.part" "$URL"; then
    rm -f "$DEST.part"
    echo "Could not download $URL. Are you offline? Nothing was installed; re-run when you're connected." >&2
    exit 1
  fi
  actual="$(sha256 "$DEST.part")"
  if [ "$actual" != "$SHA256" ]; then
    rm -f "$DEST.part"
    echo "Checksum mismatch for outlook-mcp-rs.exe: expected $SHA256, got $actual. Nothing was installed." >&2
    exit 1
  fi
  mv -f "$DEST.part" "$DEST"
  echo "OK: saved and verified $DEST"
fi
echo "Point OUTLOOK_MCP_BIN at it so .mcp.json / opencode.json can launch it (Windows: setx OUTLOOK_MCP_BIN \"<full path>\")."
