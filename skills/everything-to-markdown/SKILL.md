---
name: everything-to-markdown
description: Convert PDF/Word/PPT/Excel/images to Markdown locally, then read only the .md. Use for 上传文档、转 Markdown、OCR、扫描件、inbox files, office documents, WPS, or summarizing a PDF. Never send binary office/PDF or base64 to the model.
license: MIT
compatibility: Requires Python 3.10+ with markitdown. Optional ocrmypdf and tesseract for scans. Optional Microsoft Office, WPS, or LibreOffice for .doc/.wps/.xls/.ppt. Linux/macOS/Windows/WSL.
metadata:
  author: local
  version: "1.0"
  edition: portable
---

# everything-to-markdown

Binary files stay on disk. The model only reads the generated `.converted.md`. Do not `read` PDF/DOCX/PPTX/XLSX as text. Do not paste base64.

This skill is harness-agnostic. Use this agent's shell + file-read tools. Install: `references/install.md`. Timeouts: `references/harnesses.md`. Repo one-click: `../../install.sh`.

## When to use

User drops a document, gives a path, mentions inbox / 转 Markdown / OCR / 扫描件 / WPS / Office, or asks to summarize a PDF/Word file.

## Convert

```bash
bash "<skill-dir>/scripts/convert.sh" "<file>" [--mode auto|skip-text|force-ocr] [-o out.md]
bash "<skill-dir>/scripts/convert.sh" --detect-office
```

`<skill-dir>` is the folder that contains this `SKILL.md`. Never hardcode another machine's home directory.

Stdout is **one JSON object**.

| User intent | `--mode` | Behavior |
|---|---|---|
| Text / unspecified | `auto` or `skip-text` | Probe first 3 PDF pages. Text layer → markitdown only (`skip-text-direct`). Almost no text → `ocrmypdf --skip-text` (slow). |
| User said scan / screenshot / no text layer | `force-ocr` | `ocrmypdf --force-ocr` then markitdown |

Images use tesseract. Do not pass `*.converted.md`, `*_2_OCR.pdf`, or `*_3_最终.md` as input.

**Office / WPS:** `docx`/`xlsx`/`pptx` → markitdown. `.doc` `.xls` `.ppt` `.rtf` and WPS `.wps` `.et` `.dps` are converted to OOXML first. Auto-detect prefers the app bound to `.docx` (WPS vs Microsoft Office), then LibreOffice. Override: `DOC2MD_OFFICE=wps|msoffice|libreoffice`. JSON includes `office`.

Default output: `<stem>.converted.md` next to the source.

Run the repo `./install.sh` for venv + markitdown + optional ocrmypdf + skill links. `DOC2MD_PYTHON` overrides the interpreter. `DOC2MD_OCR_LANG` defaults to `chi_sim+fra+eng`.

## Agent checklist

1. **Pick the file.** Named path wins. Otherwise originals in `inbox/` (skip README and generated files).
2. **`ls -lh`** for size. Unspecified scan → `--mode skip-text`.
3. **Run the script.** `timeout_hint` is `short` or `long`. If this harness kills a command around 60s, start long jobs in **that harness's background API**. Do not bump a foreground timeout and rerun.
4. **Parse JSON.** Use `markdown`. If missing/garbled, glob `*.converted.md` next to the source.
5. **Read only that Markdown.** Long files: first ~200 lines, then sections.
6. **Reply with** the command, md path, `mode`/`engine`, and `office.preferred` when present.

## Hard rules

- Text-layer PDFs: never `--force-ocr` unless the user said scan/screenshot.
- On JSON `error`: report it. Do not ingest the original binary.
- Chat-dropped **images** meant as OCR: run this script, then read the md. Do not feed large images as vision by default.
