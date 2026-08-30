# everything-to-markdown

Agent skill: convert PDF / Word / PPT / Excel / images to Markdown **on disk**, then the model reads only `.converted.md`.

Detects whether the machine uses **Microsoft Office** or **WPS** (and LibreOffice as fallback) and uses that suite to open `.doc` / `.wps` / `.xls` / `.ppt` before extraction.

###「聊天式AI（非自主Agent）用户不要读下面的 Agent 安装，只复制 CHAT_PROMPT.md。」

Layout matches [Agent Skills](https://agentskills.io/specification) / [skills.sh](https://skills.sh/) (`skills/<name>/SKILL.md`).

## One-click

```bash
git clone https://github.com/ThomasAchilleShao/everything-to-markdown.git
cd everything-to-markdown
chmod +x install.sh
./install.sh
```

Windows (PowerShell):

```powershell
git clone https://github.com/ThomasAchilleShao/everything-to-markdown.git
cd everything-to-markdown
.\install.ps1
```

网页聊天用户不要自己写 `.bat`。`.\install.ps1 -Agents ""` 会按 `desktop\` 里的模板，在桌面生成「普通转换.bat」（装了 Tesseract 时还有「扫描转换.bat」）。图标丢了只跑：

```powershell
.\install.ps1 -DesktopOnly -Agents ""
```

This will:

1. Create `.venv` and `pip install` **markitdown** + **pdfminer**
2. Install **ocrmypdf** (Tesseract/Ghostscript still need a system install; `./install.sh --system-ocr` tries apt/brew/winget)
3. Detect Office vs WPS → `office-detect.json`
4. Symlink the skill into `~/.claude/skills`, `~/.codex/skills`, `~/.grok/skills`, `~/.cursor/skills`
5. On Windows, write drag-and-drop bats to the Desktop from `desktop/` templates

Opt in to DSH: `./install.sh --agents dsh` (will not replace an existing skill unless `--force`).

Skill-only (no venv), via [skills.sh](https://skills.sh/):

```bash
npx skills add ThomasAchilleShao/everything-to-markdown --skill everything-to-markdown
./install.sh --agents claude   # still run this for markitdown/OCR
```

## Convert

```bash
bash skills/everything-to-markdown/scripts/convert.sh --detect-office
bash skills/everything-to-markdown/scripts/convert.sh /path/to/file.pdf --mode skip-text
```

Stdout is one JSON object. Read the path in `markdown`.

| File | Path |
|---|---|
| Skill | `skills/everything-to-markdown/SKILL.md` |
| Install into agents | `skills/everything-to-markdown/references/install.md` |
| Timeouts per harness | `skills/everything-to-markdown/references/harnesses.md` |

`DOC2MD_OFFICE=wps|msoffice|libreoffice` overrides auto-detect.
