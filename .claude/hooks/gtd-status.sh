#!/usr/bin/env bash
# SessionStart hook: prints a GTD brief (same as the gtd-status skill). Read-only.
set -uo pipefail
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then VAULT="$CLAUDE_PROJECT_DIR"
else VAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; fi
cd "$VAULT" 2>/dev/null || exit 0

inbox_count=0
[[ -d "00 Inbox" ]] && inbox_count=$(find "00 Inbox" -maxdepth 1 -type f -name '*.md' ! -name 'README.md' 2>/dev/null | wc -l | tr -d ' ')

review_line="⚠️  No weekly review found yet — run /gtd-weekly-review"
if [[ -d "Journal" ]]; then
  last=$(grep -rl "weekly-review" "Journal" --include='*.md' 2>/dev/null | grep -v '/README.md$' | xargs -r ls -t 2>/dev/null | head -1)
  if [[ -n "$last" ]]; then
    now=$(date +%s); mt=$(date -r "$last" +%s 2>/dev/null || echo "$now"); days=$(( (now-mt)/86400 ))
    if (( days>=7 )); then review_line="⚠️  Weekly review is ${days} days old — run /gtd-weekly-review"
    else review_line="✅ Weekly review done ${days}d ago"; fi
  fi
fi

dirs=(); for d in "00 Inbox" "10 Projects" "20 Areas" "Journal" "People" "Meetings"; do [[ -d "$d" ]] && dirs+=("$d"); done
next=""
if (( ${#dirs[@]} > 0 )); then
  next=$(grep -rh '^[[:space:]]*- \[ \].*#next' "${dirs[@]}" --include='*.md' 2>/dev/null \
    | grep -v '#waiting' \
    | sed -E 's/^[[:space:]]*- \[ \][[:space:]]*//; s/\[\[([^]]*)\]\]/\1/g; s/\[[a-z]+:: ?[^]]*\]//g; s/#[A-Za-z_-]+//g; s/[[:space:]]+/ /g; s/^ //; s/ $//' \
    | grep -v '^$' | head -5)
fi

proj=0; [[ -d "10 Projects" ]] && proj=$(grep -rls 'status: active' "10 Projects" --include='*.md' 2>/dev/null | wc -l | tr -d ' ')

echo "🧠 Second Brain — GTD status"
echo "📥 Inbox: ${inbox_count} item(s) · 📋 ${proj} active project(s)"
echo "$review_line"
if [[ -n "$next" ]]; then echo "⚡ Next actions ready:"; while IFS= read -r a; do echo "   • $a"; done <<< "$next"
else echo "⚡ No #next actions queued — try /gtd-process-inbox or /gtd-weekly-review."; fi
