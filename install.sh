#!/usr/bin/env bash
# One-click installer: venv + markitdown + optional OCR + Office/WPS detect + agent skill links.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$ROOT/skills/everything-to-markdown"
VENV="$ROOT/.venv"

AGENTS="claude,codex,grok,cursor"
WITH_DEPS=1
WITH_OCR=1
WITH_SYSTEM=0
FORCE=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --agents list   comma list: claude,codex,grok,cursor,dsh  (default: claude,codex,grok,cursor)
                  'all' = those four. 'dsh' is opt-in so a local DSH skill is not overwritten.
  --no-deps       skip pip/venv
  --no-ocr        skip ocrmypdf pip package
  --system-ocr    also try apt/brew/winget for tesseract + ghostscript (may prompt)
  --force         replace existing skill directories
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agents) AGENTS="${2:-}"; shift 2 ;;
    --no-deps) WITH_DEPS=0; shift ;;
    --no-ocr) WITH_OCR=0; shift ;;
    --system-ocr) WITH_SYSTEM=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$AGENTS" == "all" ]]; then
  AGENTS="claude,codex,grok,cursor"
fi

pick_python() {
  local c
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      command -v "$c"
      return
    fi
  done
  shopt -s nullglob
  for c in /mnt/c/Users/*/AppData/Local/Python/pythoncore-*/python.exe \
           /mnt/c/Users/*/AppData/Local/Programs/Python/Python*/python.exe; do
    if [[ -x "$c" ]]; then
      printf '%s' "$c"
      shopt -u nullglob
      return
    fi
  done
  shopt -u nullglob
  echo "need python3" >&2
  exit 1
}

install_system_ocr() {
  if command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim tesseract-ocr-fra ghostscript || true
    return
  fi
  if command -v brew >/dev/null 2>&1; then
    brew install tesseract tesseract-lang ghostscript || true
    return
  fi
  if command -v winget.exe >/dev/null 2>&1; then
    winget.exe install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements || true
    winget.exe install --id ArtifexSoftware.GhostScript -e --accept-package-agreements --accept-source-agreements || true
  fi
}

if [[ "$WITH_SYSTEM" -eq 1 ]]; then
  install_system_ocr
fi

PY="$(pick_python)"
if [[ "$WITH_DEPS" -eq 1 ]]; then
  if [[ "$PY" == *.exe ]]; then
    "$PY" -m venv "$VENV"
    VPY="$VENV/Scripts/python.exe"
    [[ -x "$VPY" ]] || VPY="$VENV/bin/python"
  else
    "$PY" -m venv "$VENV"
    VPY="$VENV/bin/python"
    [[ -x "$VPY" ]] || VPY="$VENV/Scripts/python.exe"
  fi
  "$VPY" -m pip install -U pip
  "$VPY" -m pip install -r "$ROOT/requirements.txt"
  if [[ "$WITH_OCR" -eq 1 ]]; then
    "$VPY" -m pip install -r "$ROOT/requirements-ocr.txt" || "$VPY" -m pip install ocrmypdf || true
  fi
else
  VPY="$PY"
fi

mkdir -p "$SKILL_SRC"
printf '%s\n' "$(cd "$(dirname "$VPY")" && pwd)/$(basename "$VPY")" > "$SKILL_SRC/.doc2md-python"

chmod +x "$SKILL_SRC/scripts/convert.sh" "$SKILL_SRC/scripts/convert_to_md.py" "$SKILL_SRC/scripts/office_bridge.py" || true

OFFICE_JSON="$ROOT/office-detect.json"
if "$VPY" "$SKILL_SRC/scripts/office_bridge.py" --detect > "$OFFICE_JSON" 2>/dev/null; then
  true
else
  python3 "$SKILL_SRC/scripts/office_bridge.py" --detect > "$OFFICE_JSON" || echo '{"preferred":"none","available":[]}' > "$OFFICE_JSON"
fi

link_skill() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  if [[ -e "$dest" || -L "$dest" ]]; then
    if [[ "$FORCE" -ne 1 ]]; then
      echo "skip existing $dest (use --force)"
      printf '%s\n' "$(cat "$SKILL_SRC/.doc2md-python")" > "$dest/.doc2md-python" 2>/dev/null || true
      return
    fi
    rm -rf "$dest"
  fi
  ln -s "$SKILL_SRC" "$dest" 2>/dev/null || cp -a "$SKILL_SRC" "$dest"
  echo "installed $dest"
}

IFS=',' read -ra AGENT_ARR <<< "$AGENTS"
for a in "${AGENT_ARR[@]}"; do
  a="$(echo "$a" | tr -d '[:space:]')"
  [[ -z "$a" ]] && continue
  case "$a" in
    claude) link_skill "$HOME/.claude/skills/everything-to-markdown" ;;
    codex) link_skill "$HOME/.codex/skills/everything-to-markdown" ;;
    grok) link_skill "$HOME/.grok/skills/everything-to-markdown" ;;
    cursor) link_skill "$HOME/.cursor/skills/everything-to-markdown" ;;
    dsh)
      DSH_DEST="${DSH_SKILLS:-$HOME/.agents/skills/everything-to-markdown}"
      link_skill "$DSH_DEST"
      ;;
    *) echo "unknown agent: $a" >&2 ;;
  esac
done

echo
echo "Python: $VPY"
echo "Office/WPS:"
cat "$OFFICE_JSON"
echo
echo "Try: bash \"$SKILL_SRC/scripts/convert.sh\" --detect-office"
echo "Then: bash \"$SKILL_SRC/scripts/convert.sh\" /path/to/file.pdf --mode skip-text"
echo
echo "If you cloned from GitHub, also: npx skills add ThomasAchilleShao/everything-to-markdown --skill everything-to-markdown"
