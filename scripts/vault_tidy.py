#!/usr/bin/env python3
"""Keep the vault small so agents (especially light LLMs) read less. Deterministic, stdlib only.

DRY-RUN by default: prints the plan. Add --apply to do it. Never deletes a note; it only moves
things into `40 Archive/` (which the dashboards, skills and the session brief don't scan).

    python scripts/vault_tidy.py                       # show the plan
    python scripts/vault_tidy.py --apply               # do it
    python scripts/vault_tidy.py --apply --only projects,transcripts

Steps (all skip anything with an open `- [ ]` task, so nothing actionable disappears):
  projects     `10 Projects/*` with `status: done`            → `40 Archive/Projects/`
  meetings     `Meetings/*` summarized, older than --meeting-days (90) → `40 Archive/Meetings/`
  journal      `Journal/*` dailies older than --journal-days (60), not the newest weekly review
                                                               → `40 Archive/Journal/`
  transcripts  the `## Transcript` body of summarized meetings bigger than --transcript-chars
               (4000) moves to `40 Archive/Transcripts/<note> transcript.md`, leaving a link —
               the single biggest context saver: transcripts dwarf everything else in the vault.
  inbox        empty (whitespace-only) files in `00 Inbox/` are reported (not removed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

OPEN_TASK_LINE = re.compile(r"^\s*-\s*\[ \]\s*(.*)$")
DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")
STEPS = ("projects", "meetings", "journal", "transcripts", "inbox")


def fm(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"')
    return out


def has_open_task(text: str) -> bool:
    # an unfilled template line like "- [ ]  #next" is not a real task
    for line in text.splitlines():
        m = OPEN_TASK_LINE.match(line)
        if m and re.sub(r"#[A-Za-z][\w-]*|\[[a-z][\w-]*::[^\]]*\]", "", m.group(1)).strip():
            return True
    return False


def note_date(p: Path, meta: dict) -> dt.date | None:
    for s in (meta.get("date"), meta.get("created"), p.stem[:10]):
        m = DATE_PREFIX.match(s or "")
        if m:
            try:
                return dt.date.fromisoformat(m.group(1))
            except ValueError:
                pass
    return None


def notes(vault: Path, folder: str, recursive: bool = False) -> list[Path]:
    base = vault / folder
    if not base.is_dir():
        return []
    it = base.rglob("*.md") if recursive else base.glob("*.md")
    return sorted(p for p in it if p.name != "README.md")


def unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    i = 2
    while True:
        cand = dest.with_name(f"{dest.stem} ({i}){dest.suffix}")
        if not cand.exists():
            return cand
        i += 1


def plan(vault: Path, a) -> list[tuple[str, Path, Path | None, str]]:
    """[(step, source, destination-or-None, why)]"""
    today = dt.date.today()
    out = []
    if "projects" in a.only:
        for p in notes(vault, "10 Projects", recursive=True):
            t = p.read_text(encoding="utf-8")
            if fm(t).get("status") == "done":
                if has_open_task(t):
                    out.append(("projects", p, None, "status: done but has open tasks — left in place"))
                else:
                    out.append(("projects", p, vault / "40 Archive/Projects" / p.name, "status: done"))
    if "meetings" in a.only:
        for p in notes(vault, "Meetings"):
            t = p.read_text(encoding="utf-8")
            m = fm(t)
            d = note_date(p, m)
            if m.get("summary_status") == "done" and d and (today - d).days > a.meeting_days \
                    and not has_open_task(t):
                out.append(("meetings", p, vault / "40 Archive/Meetings" / p.name,
                            f"summarized, {(today - d).days}d old, no open tasks"))
    if "journal" in a.only:
        reviews = [p for p in notes(vault, "Journal") if "weekly-review" in p.read_text(encoding="utf-8")]
        newest_review = max(reviews, key=lambda p: p.stat().st_mtime) if reviews else None
        for p in notes(vault, "Journal"):
            if p == newest_review:
                continue
            t = p.read_text(encoding="utf-8")
            d = note_date(p, fm(t))
            if d and (today - d).days > a.journal_days and not has_open_task(t):
                out.append(("journal", p, vault / "40 Archive/Journal" / p.name,
                            f"{(today - d).days}d old, no open tasks"))
    if "transcripts" in a.only:
        archiving = {src for step, src, dest, _ in out if dest is not None}
        for p in notes(vault, "Meetings"):
            if p in archiving:  # the whole note is leaving the hot path already
                continue
            t = p.read_text(encoding="utf-8")
            if fm(t).get("summary_status") != "done":
                continue
            body = section(t, "## Transcript")
            if body and len(body.strip()) > a.transcript_chars:
                out.append(("transcripts", p,
                            vault / "40 Archive/Transcripts" / f"{p.stem} transcript.md",
                            f"transcript {len(body.strip())} chars"))
    if "inbox" in a.only:
        base = vault / "00 Inbox"
        if base.is_dir():
            for p in sorted(base.glob("*.md")):
                if p.name != "README.md" and not p.read_text(encoding="utf-8").strip():
                    out.append(("inbox", p, None, "empty capture — delete it yourself if unwanted"))
    return out


def section(text: str, heading: str) -> str | None:
    """Body under `heading` up to the next `## ` heading (None if absent)."""
    lines = text.split("\n")
    try:
        i = next(n for n, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        return None
    j = next((n for n in range(i + 1, len(lines)) if lines[n].startswith("## ")), len(lines))
    return "\n".join(lines[i + 1:j])


def move_transcript(src: Path, dest: Path) -> Path:
    text = src.read_text(encoding="utf-8")
    body = section(text, "## Transcript") or ""
    dest = unique(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"---\ntype: transcript\nmeeting: \"[[{src.stem}]]\"\n---\n\n"
                    f"# {src.stem} — transcript\n{body.rstrip()}\n", encoding="utf-8")
    link = f"\n_Moved to [[{dest.stem}]] by vault_tidy (summary above is the working copy)._\n"
    lines = text.split("\n")
    i = next(n for n, l in enumerate(lines) if l.strip() == "## Transcript")
    j = next((n for n in range(i + 1, len(lines)) if lines[n].startswith("## ")), len(lines))
    new = "\n".join(lines[: i + 1]) + link + ("\n" + "\n".join(lines[j:]) if j < len(lines) else "")
    src.write_text(new, encoding="utf-8")
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Archive finished material so agents read less.")
    ap.add_argument("--vault", help="vault root (default: this repo)")
    ap.add_argument("--apply", action="store_true", help="do it (default: dry run)")
    ap.add_argument("--only", default=",".join(STEPS), help="comma list of: " + ",".join(STEPS))
    ap.add_argument("--meeting-days", type=int, default=90)
    ap.add_argument("--journal-days", type=int, default=60)
    ap.add_argument("--transcript-chars", type=int, default=4000)
    a = ap.parse_args(argv)
    a.only = {s.strip() for s in a.only.split(",") if s.strip()}
    bad = a.only - set(STEPS)
    if bad:
        ap.error("unknown step(s): " + ", ".join(sorted(bad)))
    vault = Path(a.vault) if a.vault else Path(__file__).resolve().parents[1]
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    items = plan(vault, a)
    actions = [x for x in items if x[2] is not None]
    print(("APPLY" if a.apply else "DRY RUN") + f": {len(actions)} change(s), "
          f"{len(items) - len(actions)} note(s) to look at")
    for step, src, dest, why in items:
        rel = src.relative_to(vault).as_posix()
        if dest is None:
            print(f"  NOTE  {step:<11} {rel} — {why}")
            continue
        drel = dest.relative_to(vault).as_posix()
        if a.apply:
            if step == "transcripts":
                drel = move_transcript(src, dest).relative_to(vault).as_posix()
            else:
                dest = unique(dest)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                drel = dest.relative_to(vault).as_posix()
        print(f"  {'DONE' if a.apply else 'PLAN'}  {step:<11} {rel} → {drel} ({why})")
    if actions and not a.apply:
        print("Run again with --apply to do it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
