# Harness differences (timeouts, tools, attachments)

The converter is the same. Only how the **agent** launches it changes.

`timeout_hint` from JSON:

- `short` — text extract / office markitdown. Foreground is usually fine.
- `long` — ocrmypdf or tesseract. Minutes are normal for multi-page scans.

## If the shell dies around 60 seconds

Start long jobs in the background **with that product's API**, then wait for the JSON line. Do not raise a foreground timeout and rerun the same command.

Examples (do not mix names across products):

- DSH: `run_in_background: true` on bash, then `job_output` with `wait: true`
- Claude Code: background Bash / wait for the task id
- Codex: equivalent background shell
- Grok Build / WorkBuddy / Cursor: use that CLI's job or long-timeout shell

## If the shell can run for several minutes

Foreground is OK. Still prefer background for OCR so the user sees progress.

## Attachments

- Some UIs accept PDF/Word in chat. Save or use the given workspace path, then run `convert.sh`.
- Some UIs (including DSH) only accept images. A project `inbox/` folder is a practical drop zone; skip generated `*.converted.md` and `*_2_OCR.pdf`.

## Paths

- Pass POSIX paths into `convert.sh` on Linux/macOS/WSL.
- On native Windows, pass Windows paths or run the `.py` with a UTF-8 Python: `python scripts/convert_to_md.py <file>`.
- JSON `markdown` is the path the agent should open. If WSL + Windows Python garbles CJK, glob `*.converted.md` beside the source.

## DSH

This published package is `everything-to-markdown`. `./install.sh --agents dsh` links it to `~/.agents/skills/everything-to-markdown` and will not overwrite another skill unless you pass `--force`.
