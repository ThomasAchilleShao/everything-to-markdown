#!/usr/bin/env bash
# Portable entry: prefer install.sh venv, then any Python with markitdown.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/convert_to_md.py"

to_win() {
  local p="$1"
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -w "$p"
  else
    printf '%s' "$p"
  fi
}

python_has_markitdown() {
  local py="$1"
  [[ -n "$py" ]] || return 1
  "$py" -c "import markitdown" >/dev/null 2>&1
}

venv_pythons() {
  local d
  for d in \
    "$SCRIPT_DIR/../.venv" \
    "$SCRIPT_DIR/../../../.venv" \
    "$SCRIPT_DIR/../../.venv"
  do
    if [[ -x "$d/bin/python" ]]; then
      printf '%s\n' "$d/bin/python"
    fi
    if [[ -x "$d/Scripts/python.exe" ]]; then
      printf '%s\n' "$d/Scripts/python.exe"
    fi
  done
  if [[ -f "$SCRIPT_DIR/../.doc2md-python" ]]; then
    cat "$SCRIPT_DIR/../.doc2md-python"
    printf '\n'
  fi
}

find_python() {
  if [[ -n "${DOC2MD_PYTHON:-}" ]]; then
    if python_has_markitdown "${DOC2MD_PYTHON}"; then
      printf '%s' "${DOC2MD_PYTHON}"
      return
    fi
  fi

  local vpy
  while IFS= read -r vpy; do
    [[ -z "$vpy" ]] && continue
    if python_has_markitdown "$vpy"; then
      printf '%s' "$vpy"
      return
    fi
  done < <(venv_pythons)

  local cmd
  for cmd in python3 python py; do
    if command -v "$cmd" >/dev/null 2>&1 && python_has_markitdown "$(command -v "$cmd")"; then
      command -v "$cmd"
      return
    fi
  done

  local c
  shopt -s nullglob
  for c in \
    /mnt/c/Users/*/AppData/Local/Python/pythoncore-*/python.exe \
    /mnt/c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    /usr/local/bin/python3 \
    /opt/homebrew/bin/python3
  do
    if [[ -x "$c" ]] && python_has_markitdown "$c"; then
      printf '%s' "$c"
      shopt -u nullglob
      return
    fi
  done
  shopt -u nullglob

  echo '{"ok":false,"error":"no python with markitdown; run ./install.sh or pip install markitdown"}' >&2
  exit 1
}

abs_path() {
  local p="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$p"
  else
    readlink -f "$p" 2>/dev/null || printf '%s' "$p"
  fi
}

if [[ "${1:-}" == "--detect-office" ]]; then
  PY_DETECT=""
  if [[ -n "${DOC2MD_PYTHON:-}" && -x "${DOC2MD_PYTHON}" ]]; then
    PY_DETECT="${DOC2MD_PYTHON}"
  elif command -v python3 >/dev/null 2>&1; then
    PY_DETECT="$(command -v python3)"
  else
    PY_DETECT="$(find_python)"
  fi
  exec "$PY_DETECT" "$SCRIPT_DIR/office_bridge.py" --detect
fi

PY="$(find_python)"
ARGS=()
POSIX_INPUT=""
POSIX_OUTPUT=""
prev=""
NEED_WIN=0
if [[ "$PY" == *.exe ]] && command -v wslpath >/dev/null 2>&1; then
  NEED_WIN=1
fi

for arg in "$@"; do
  if [[ "$prev" == "-o" || "$prev" == "--output" ]]; then
    POSIX_OUTPUT="$(abs_path "$arg")"
  fi
  if [[ "$arg" == /* || "$arg" == ./* || "$arg" == ../* ]]; then
    if [[ -z "$POSIX_INPUT" && "$prev" != "-o" && "$prev" != "--output" ]]; then
      POSIX_INPUT="$(abs_path "$arg")"
    fi
    if [[ "$NEED_WIN" -eq 1 ]]; then
      ARGS+=("$(to_win "$arg")")
    else
      ARGS+=("$arg")
    fi
  else
    ARGS+=("$arg")
  fi
  prev="$arg"
done

if [[ -n "$POSIX_INPUT" && -z "$POSIX_OUTPUT" ]]; then
  base="$(basename "$POSIX_INPUT")"
  stem="${base%.*}"
  POSIX_OUTPUT="$(dirname "$POSIX_INPUT")/${stem}.converted.md"
fi

export DOC2MD_POSIX_INPUT="${POSIX_INPUT}"
export DOC2MD_POSIX_OUTPUT="${POSIX_OUTPUT}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if [[ "$NEED_WIN" -eq 1 ]]; then
  PY_SCRIPT_ARG="$(to_win "$PY_SCRIPT")"
  for d in /mnt/c/Users/Public /tmp "$SCRIPT_DIR"; do
    if [[ -d "$d" && -w "$d" ]]; then
      cd "$d"
      break
    fi
  done
else
  PY_SCRIPT_ARG="$PY_SCRIPT"
fi

exec "$PY" "$PY_SCRIPT_ARG" "${ARGS[@]}"
