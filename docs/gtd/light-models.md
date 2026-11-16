# Running the vault on light / small-context models

If you drive the vault with a fast, cheap model (DeepSeek Flash, Haiku-class, a local model) and it
**compacts several times per task**, the context is filling with things the task doesn't need.
This kit fixes the usual causes.

## What was eating the context
| Cause | Cost | Fix |
| --- | --- | --- |
| 14 vendored developer skills (Superpowers) — their descriptions load every session, and `using-superpowers` / `brainstorming` tell the model to open skills before replying | ~1–2k tokens per session just for the list; 4–8k per skill opened (some are 30k+) | `lean_mode.py on` parks them |
| Grepping / reading whole folders to find tasks | every note read stays in context | `scripts/gtd_query.py` prints only the lines needed |
| Meeting transcripts (often 10–50k tokens each) | one summary can fill a small window | `meeting-summarizer` subagent + `vault_tidy.py` moves summarized transcripts to `40 Archive/Transcripts/` |
| Outlook MCP tool schemas | every turn | lean mode disables the server (`--keep-outlook` to keep it) |
| Noisy command output | unbounded | lean mode caps Bash at 12k chars, MCP at 6k tokens |

## Messages are usually the bulk
`/context` may show skills, memory and MCP at only a few thousand tokens. What fills a 256k window is
the conversation itself: every file the model reads, every command's output, every file it
rewrites, and its own replies and thinking all stay in the context until it compacts.

**Measure it.** After a session that compacted:
```
python3 scripts/context_report.py          # latest session of this vault
python3 scripts/context_report.py --list   # pick another one
```
It reads the session transcript Claude Code keeps under `~/.claude/projects/` and shows where the
message tokens went (tool results by tool and file, model replies, thinking, Write bodies,
attachments), files read more than once, the turns where the context jumped most, and suggestions.

**What lean mode does about it:**
| Message cost | Lean mode |
| --- | --- |
| Whole-file reads of big notes | Guard hook (`.claude/hooks/lean_guard.py`) blocks a Read of a file over 12 KB without `limit`, and tells the model to use `gtd_query.py`, Grep -n or offset/limit. An explicit `limit` is the way through when it really needs the whole file. `LEAN_GUARD_MAX_BYTES` changes the size. |
| `cat` of big files, `ls -R`, `tree` | Same hook, same advice. |
| Rewriting whole files with Write | Same hook blocks Write over an existing big file: use Edit. |
| Long replies, narration, echoing output | `GTD Lean` output style (`.claude/output-styles/gtd-lean.md`). It also drops Claude Code's software-engineering instructions from the system prompt. |
| Command and MCP output | `BASH_MAX_OUTPUT_LENGTH=12000`, `MAX_MCP_OUTPUT_TOKENS=6000`. |
| Output reserve | For a model ID Claude Code doesn't recognize it reserves 32k tokens of the window for output. Lean mode sets `CLAUDE_CODE_MAX_OUTPUT_TOKENS=12000`. |
| Wrong window size | `--context 256000` sets `CLAUDE_CODE_MAX_CONTEXT_TOKENS` so Claude Code uses your model's real window. |
| Thinking | If the report shows thinking is a big share, try `--no-thinking` (`MAX_THINKING_TOKENS=0`) and see if the answers stay good. |

## Set up (once per machine)
```
python3 scripts/lean_mode.py on --context 256000   # Windows: python scripts\lean_mode.py on --context 256000
```
Restart the session. `python3 scripts/lean_mode.py status` shows the state; `off` restores everything.
The settings go to `.claude/settings.local.json` (per-machine). Parked skills move to
`.claude/skills-dev/` and are marked skip-worktree, so `git status` stays clean.

## Day to day
- Start with `/gtd-status` (the session hook already prints it).
- Ask normally (`/gtd-next-actions`, `/gtd-process-inbox`, …). The GTD skills now use
  `gtd_query.py` and the subagents automatically.
- **One task per session.** Run `/clear` when you switch task — cheaper than letting it compact.
- Every week or two: `/gtd-organize` (dry run first, then apply). Or schedule the
  `vault-organizer` agent with your harness's scheduler, report-only.

## The pieces
| Piece | What it does |
| --- | --- |
| `AGENTS.md` → "Context budget" | six rules the agent sees every turn |
| `scripts/gtd_query.py` | `brief next waiting inbox projects health meetings find sizes` — compact, read-only |
| `scripts/vault_tidy.py` | dry-run/`--apply` archive of done projects, old meetings/dailies, long transcripts |
| `scripts/lean_mode.py` | `on / off / status` |
| `scripts/context_report.py` | where a session's context went |
| `.claude/hooks/lean_guard.py` | blocks whole-file reads, dumps and rewrites of big files (lean mode) |
| `.claude/output-styles/gtd-lean.md` | short replies (lean mode) |
| `.claude/agents/vault-scout.md` | read-only lookups, ≤15-line answers |
| `.claude/agents/inbox-triage.md` | one-line-per-item filing plan for the inbox |
| `.claude/agents/meeting-summarizer.md` | summarizes one meeting; transcript stays out of the main chat |
| `.claude/agents/vault-organizer.md` | runs health + tidy, reports in ≤20 lines |
| skills `gtd-organize`, `gtd-lean-mode` | the user-facing entry points |

Subagents use the same model as the session (`model: inherit`). opencode defines subagents in
`.opencode/agent/` with its own frontmatter; the bodies of these four files can be reused there.
Without subagents the skills fall back to running the scripts directly.

## Harness tips for DeepSeek via Claude Code
- Use a model setting with the largest context the provider offers; set
  `CLAUDE_CODE_MAX_OUTPUT_TOKENS` modestly (e.g. 8000) so replies don't eat the window.
- If your proxy maps a "small/fast" model, point `ANTHROPIC_DEFAULT_HAIKU_MODEL` (older versions:
  `ANTHROPIC_SMALL_FAST_MODEL`) at the Flash model for background work.
- `/compact` with a focus ("/compact keep only the inbox plan") beats automatic compaction.
