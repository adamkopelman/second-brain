#!/usr/bin/env bash
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gtd-status.sh"
fail=0; ac(){ grep -qF "$2" <<<"$1" && echo "OK  $3" || { echo "FAIL $3"; fail=1; }; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/00 Inbox" "$TMP/10 Projects" "$TMP/Journal"
echo "- [ ] loose" > "$TMP/00 Inbox/x.md"
printf '%s\n' '---' 'status: active' '---' \
  '- [ ] Pick SSG #next #computer [due:: 2026-09-15] [[P]]' \
  '- [ ] Wait domain #waiting [[Reg]] [since:: 2026-09-02]' > "$TMP/10 Projects/P.md"
out="$(CLAUDE_PROJECT_DIR="$TMP" bash "$HOOK")"
ac "$out" "Inbox: 1" "inbox count"; ac "$out" "1 active project" "active projects"
ac "$out" "Pick SSG" "next surfaced"
grep -q "Wait domain" <<<"$out" && { echo "FAIL waiting excluded"; fail=1; } || echo "OK  waiting excluded"
ac "$out" "No weekly review" "review none"
E="$(mktemp -d)"; o2="$(CLAUDE_PROJECT_DIR="$E" bash "$HOOK")"; rm -rf "$E"; ac "$o2" "Inbox: 0" "empty vault"
exit $fail
