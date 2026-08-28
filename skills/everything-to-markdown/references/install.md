# Install

From the **repository root** (venv + markitdown + optional OCR + Office/WPS detect + skill links):

```bash
./install.sh
# Windows: .\install.ps1
```

This folder is the skill package (`SKILL.md` here). `install.sh` links it to:

| Harness | User dir |
|---|---|
| Claude Code | `~/.claude/skills/everything-to-markdown` |
| Codex CLI | `~/.codex/skills/everything-to-markdown` |
| Grok Build | `~/.grok/skills/everything-to-markdown` |
| Cursor | `~/.cursor/skills/everything-to-markdown` |
| WorkBuddy / CodeBuddy | that product's skills dir, or copy this folder |
| DSH | `./install.sh --agents dsh` (opt-in; will not overwrite without `--force`) |

Public GitHub repos with `skills/*/SKILL.md` are indexed by [skills.sh](https://skills.sh/):

```bash
npx skills add <owner>/<repo> --skill everything-to-markdown
```

Still run `./install.sh` so markitdown/OCR are present.

Do not nest: installed path must be `.../everything-to-markdown/SKILL.md`.

Format: [Agent Skills specification](https://agentskills.io/specification).
