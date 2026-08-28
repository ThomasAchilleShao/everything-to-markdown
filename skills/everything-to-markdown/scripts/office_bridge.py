#!/usr/bin/env python3
"""Detect Microsoft Office / WPS / LibreOffice and convert legacy/WPS files to OOXML."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path

NEED_BRIDGE = {
    ".doc",
    ".dot",
    ".rtf",
    ".wps",
    ".wpt",
    ".xls",
    ".xlt",
    ".et",
    ".ett",
    ".ppt",
    ".pps",
    ".dps",
    ".dpt",
}
OOXML = {".docx", ".xlsx", ".pptx"}
TARGET = {
    ".doc": "docx",
    ".dot": "docx",
    ".rtf": "docx",
    ".wps": "docx",
    ".wpt": "docx",
    ".xls": "xlsx",
    ".xlt": "xlsx",
    ".et": "xlsx",
    ".ett": "xlsx",
    ".ppt": "pptx",
    ".pps": "pptx",
    ".dps": "pptx",
    ".dpt": "pptx",
}

WPS_WORD = ("KWps.Application", "wps.Application", "WPS.Application")
WPS_EXCEL = ("KEt.Application", "ket.Application", "ET.Application")
WPS_PPT = ("KWPP.Application", "wpp.Application", "WPP.Application")


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)


def _exists(p: str | Path) -> bool:
    try:
        return Path(p).is_file()
    except OSError:
        return False


def _first_glob(*patterns: str) -> str | None:
    for pat in patterns:
        for hit in glob(pat):
            if _exists(hit):
                return hit
    return None


def to_windows_path(path: Path) -> str:
    s = str(path.resolve())
    if s.startswith("/mnt/") and len(s) >= 7 and s[6] == "/":
        return f"{s[5].upper()}:\\" + s[7:].replace("/", "\\")
    if shutil.which("wslpath") and s.startswith("/"):
        proc = _run(["wslpath", "-w", s], timeout=10)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return s


def _powershell() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")


def _assoc_progid(ext: str) -> str:
    ps = _powershell()
    if not ps:
        return ""
    key = ext if ext.startswith(".") else f".{ext}"
    script = (
        f"$p='HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{key}\\UserChoice';"
        "try{(Get-ItemProperty $p -ErrorAction Stop).ProgId}catch{''}"
    )
    proc = _run([ps, "-NoProfile", "-STA", "-Command", script], timeout=20)
    return (proc.stdout or "").strip()


def detect() -> dict:
    word = _first_glob(
        "/mnt/c/Program Files/Microsoft Office/root/Office16/WINWORD.EXE",
        "/mnt/c/Program Files/Microsoft Office/Office16/WINWORD.EXE",
        "/mnt/c/Program Files (x86)/Microsoft Office/root/Office16/WINWORD.EXE",
        r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        r"C:\Program Files\Microsoft Office\Office16\WINWORD.EXE",
    )
    wps = _first_glob(
        "/mnt/c/Program Files/Kingsoft/WPS Office/*/office6/wps.exe",
        "/mnt/c/Program Files/WPS Office/*/office6/wps.exe",
        "/mnt/c/Users/*/AppData/Local/Kingsoft/WPS Office/*/office6/wps.exe",
        r"C:\Program Files\Kingsoft\WPS Office\*\office6\wps.exe",
        r"C:\Users\*\AppData\Local\Kingsoft\WPS Office\*\office6\wps.exe",
    )
    soffice = (
        shutil.which("soffice")
        or shutil.which("libreoffice")
        or _first_glob(
            "/mnt/c/Program Files/LibreOffice/program/soffice.exe",
            r"C:\Program Files\LibreOffice\program\soffice.exe",
        )
    )
    available: list[str] = []
    paths: dict[str, str] = {}
    if wps:
        available.append("wps")
        paths["wps"] = wps
    if word:
        available.append("msoffice")
        paths["msoffice"] = word
    if soffice:
        available.append("libreoffice")
        paths["libreoffice"] = soffice

    assoc = _assoc_progid(".docx")
    preferred = (os.environ.get("DOC2MD_OFFICE") or "auto").strip().lower()
    if preferred in {"auto", "", "detect"}:
        low = assoc.lower()
        if "wps" in low or "kwps" in low or "kingsoft" in low:
            preferred = "wps"
        elif "word" in low or "office" in low:
            preferred = "msoffice"
        elif "wps" in available:
            preferred = "wps"
        elif "msoffice" in available:
            preferred = "msoffice"
        elif "libreoffice" in available:
            preferred = "libreoffice"
        else:
            preferred = "none"
    if preferred not in available and preferred != "none":
        preferred = available[0] if available else "none"

    return {
        "preferred": preferred,
        "available": available,
        "paths": paths,
        "docx_assoc": assoc,
        "override": os.environ.get("DOC2MD_OFFICE") or None,
    }


def _com_convert(engine: str, src: Path, dest: Path) -> tuple[bool, str]:
    ps = _powershell()
    if not ps:
        return False, "powershell not found"
    ext = src.suffix.lower()
    kind = TARGET.get(ext)
    if not kind:
        return False, f"no OOXML mapping for {ext}"
    src_win = to_windows_path(src).replace("`", "``").replace('"', '`"')
    dest_win = to_windows_path(dest).replace("`", "``").replace('"', '`"')
    dest.parent.mkdir(parents=True, exist_ok=True)

    if kind == "docx":
        progids = WPS_WORD if engine == "wps" else ("Word.Application",)
        fmt, collection, open_expr, save_expr, close_expr = (
            12,
            "Documents",
            '$doc = $app.Documents.Open("{src}")',
            '$doc.SaveAs("{dest}", {fmt})',
            "$doc.Close()",
        )
    elif kind == "xlsx":
        progids = WPS_EXCEL if engine == "wps" else ("Excel.Application",)
        fmt, collection = 51, "Workbooks"
        open_expr = '$doc = $app.Workbooks.Open("{src}")'
        save_expr = '$doc.SaveAs("{dest}", {fmt})'
        close_expr = "$doc.Close($false)"
    else:
        progids = WPS_PPT if engine == "wps" else ("PowerPoint.Application",)
        fmt, collection = 24, "Presentations"
        open_expr = '$doc = $app.Presentations.Open("{src}", $true, $true, $false)'
        save_expr = "$doc.SaveAs(\"{dest}\", {fmt})"
        close_expr = "$doc.Close()"

    last_err = ""
    for progid in progids:
        script = f"""
$ErrorActionPreference = 'Stop'
$app = $null
try {{
  $app = New-Object -ComObject {progid}
  try {{ $app.Visible = $false }} catch {{}}
  try {{ $app.DisplayAlerts = 0 }} catch {{}}
  {open_expr.format(src=src_win)}
  {save_expr.format(dest=dest_win, fmt=fmt)}
  {close_expr}
}} catch {{
  Write-Error $_
  exit 1
}} finally {{
  if ($app -ne $null) {{
    try {{ $app.Quit() }} catch {{}}
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
  }}
}}
"""
        try:
            proc = _run([ps, "-NoProfile", "-STA", "-Command", script], timeout=180)
        except subprocess.TimeoutExpired:
            last_err = "COM convert timed out"
            continue
        if proc.returncode == 0 and dest.is_file():
            return True, progid
        last_err = (proc.stderr or proc.stdout or "")[-800:]
    return False, last_err or "COM convert failed"


def _soffice_convert(soffice: str, src: Path, dest: Path) -> tuple[bool, str]:
    outdir = dest.parent
    outdir.mkdir(parents=True, exist_ok=True)
    target = dest.suffix.lstrip(".")
    cmd = [soffice, "--headless", "--norestore", "--convert-to", target, "--outdir", str(outdir), str(src)]
    if soffice.lower().endswith(".exe") and src.as_posix().startswith("/mnt/"):
        cmd = [soffice, "--headless", "--norestore", "--convert-to", target, "--outdir", to_windows_path(outdir), to_windows_path(src)]
    try:
        proc = _run(cmd, timeout=180)
    except subprocess.TimeoutExpired:
        return False, "libreoffice timed out"
    produced = dest if dest.is_file() else src.with_name(src.stem + dest.suffix)
    if produced.is_file() and produced != dest:
        produced.replace(dest)
    if dest.is_file():
        return True, "libreoffice"
    return False, (proc.stderr or proc.stdout or "libreoffice failed")[-800:]


def convert_to_ooxml(src: Path, info: dict | None = None) -> tuple[Path, dict]:
    src = src.resolve()
    ext = src.suffix.lower()
    info = info or detect()
    meta = {
        "preferred": info.get("preferred"),
        "available": info.get("available") or [],
        "used": None,
        "preconverted": None,
        "docx_assoc": info.get("docx_assoc") or "",
    }
    if ext in OOXML or ext not in NEED_BRIDGE:
        return src, meta

    target_ext = TARGET[ext]
    dest = src.with_name(f"{src.stem}.__doc2md.{target_ext}")
    order: list[str] = []
    pref = info.get("preferred")
    if pref and pref != "none":
        order.append(pref)
    for name in ("wps", "msoffice", "libreoffice"):
        if name not in order and name in (info.get("available") or []):
            order.append(name)

    errors: list[str] = []
    for engine in order:
        ok, detail = False, ""
        if engine in {"wps", "msoffice"}:
            ok, detail = _com_convert(engine, src, dest)
        elif engine == "libreoffice":
            soffice = (info.get("paths") or {}).get("libreoffice")
            if soffice:
                ok, detail = _soffice_convert(soffice, src, dest)
        if ok:
            meta["used"] = engine
            meta["preconverted"] = str(dest)
            meta["via"] = detail
            return dest, meta
        errors.append(f"{engine}: {detail}")

    raise RuntimeError(
        "could not convert {0} to {1}; install Microsoft Office, WPS, or LibreOffice. {2}".format(
            src.name, target_ext, " | ".join(errors)[:1500]
        )
    )


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in {"--detect", "detect"}:
        print(json.dumps(detect(), ensure_ascii=False, indent=2))
        return
    print(json.dumps({"ok": False, "error": "usage: office_bridge.py --detect"}, ensure_ascii=False))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
