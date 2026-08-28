#!/usr/bin/env python3
"""Convert office/pdf/image files to Markdown. Prints one JSON object to stdout.

Works with CPython on Linux, macOS, Windows, and WSL. Optional ocrmypdf/tesseract
for scans. Default output is <stem>.converted.md next to the source.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
OCR_LANG = os.environ.get("DOC2MD_OCR_LANG", "chi_sim+fra+eng")
OCR_COMMON = [
    "--deskew",
    "--rotate-pages",
    "--jobs",
    "2",
    "--oversample",
    "350",
    "--optimize",
    "0",
    "--tesseract-pagesegmode",
    "4",
]
MIN_DIRECT_TEXT_CHARS = 400
MIN_DIRECT_TEXT_SMALL = 80
SMALL_PDF_BYTES = 2 * 1024 * 1024
DERIVATIVE_SUFFIXES = (".converted.md", "_2_OCR.pdf", "_3_最终.md")
DEFAULT_SUFFIX = os.environ.get("DOC2MD_SUFFIX", ".converted.md")


def configure_stdio() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if reconf is None:
            continue
        try:
            reconf(encoding="utf-8")
        except Exception:
            pass


def die(msg: str, **extra) -> None:
    print(json.dumps({"ok": False, "error": msg, **extra}, ensure_ascii=False), flush=True)
    raise SystemExit(1)


def which_tesseract() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    win = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if win.is_file():
        return str(win)
    return None


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, text=True, encoding="utf-8", errors="replace", capture_output=True)


def markitdown(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = run([sys.executable, "-m", "markitdown", str(src), "-o", str(dest)])
    if proc.returncode != 0 or not dest.is_file():
        die(
            "markitdown failed",
            cmd=proc.args,
            returncode=proc.returncode,
            stderr=(proc.stderr or "")[-2000:],
        )


def ocrmypdf(src: Path, dest: Path, mode: str) -> subprocess.CompletedProcess[str]:
    flag = "--force-ocr" if mode == "force-ocr" else "--skip-text"
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "ocrmypdf",
        "-l",
        OCR_LANG,
        *OCR_COMMON,
        flag,
        str(src),
        str(dest),
    ]
    return run(cmd)


def convert_image(src: Path, dest: Path) -> dict:
    tess = which_tesseract()
    if not tess:
        die("tesseract not found; install Tesseract OCR or convert a PDF/Office file")
    stem_out = dest.with_suffix("")
    proc = run([tess, str(src), str(stem_out), "-l", OCR_LANG])
    txt = Path(str(stem_out) + ".txt")
    if proc.returncode != 0 or not txt.is_file():
        die(
            "tesseract failed",
            returncode=proc.returncode,
            stderr=(proc.stderr or "")[-2000:],
        )
    dest.write_text(txt.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    txt.unlink(missing_ok=True)
    return {"engine": "tesseract", "mode": "image", "timeout_hint": "long"}


def pdf_text_probe(src: Path) -> tuple[int, str]:
    try:
        from pdfminer.high_level import extract_text
    except Exception as exc:
        return 0, f"pdfminer-missing:{exc}"
    try:
        probe = extract_text(str(src), maxpages=3) or ""
        return len(probe.strip()), "pdfminer-3p"
    except Exception as exc:
        return 0, f"pdfminer-failed:{type(exc).__name__}"


def has_enough_direct_text(n: int, src: Path) -> bool:
    if n >= MIN_DIRECT_TEXT_CHARS:
        return True
    if src.stat().st_size < SMALL_PDF_BYTES and n >= MIN_DIRECT_TEXT_SMALL:
        return True
    return n >= 120


def convert_pdf(src: Path, dest: Path, mode: str) -> dict:
    probe_chars = 0
    probe_how = None
    if mode != "force-ocr":
        probe_chars, probe_how = pdf_text_probe(src)
        if has_enough_direct_text(probe_chars, src):
            markitdown(src, dest)
            text = dest.read_text(encoding="utf-8", errors="replace")
            n = len(text.strip())
            if has_enough_direct_text(n, src) or n >= probe_chars:
                return {
                    "engine": "markitdown",
                    "mode": "skip-text-direct",
                    "ocr_pdf": None,
                    "note": "text layer present; skipped ocrmypdf",
                    "probe_chars": probe_chars,
                    "probe": probe_how,
                    "timeout_hint": "short",
                }

    ocr_pdf = src.with_name(f"{src.stem}_2_OCR.pdf")
    used = mode if mode == "force-ocr" else "skip-text"
    proc = ocrmypdf(src, ocr_pdf, used)
    if proc.returncode != 0 or not ocr_pdf.is_file():
        used = f"{used}-fallback-direct"
        markitdown(src, dest)
        md_src_ok = False
    else:
        markitdown(ocr_pdf, dest)
        md_src_ok = True
    meta = {
        "engine": "ocrmypdf+markitdown",
        "mode": used,
        "ocr_pdf": posix_or_str(ocr_pdf) if md_src_ok else None,
        "ocrmypdf_returncode": proc.returncode,
        "ocrmypdf_stderr": (proc.stderr or "")[-1500:],
        "timeout_hint": "long",
    }
    if probe_how:
        meta["probe"] = probe_how
        meta["probe_chars"] = probe_chars
    return meta


def convert_office_or_other(src: Path, dest: Path) -> dict:
    from office_bridge import NEED_BRIDGE, convert_to_ooxml, detect as detect_office

    info = detect_office()
    work = src
    office_meta = {
        "preferred": info.get("preferred"),
        "available": info.get("available") or [],
        "used": None,
        "preconverted": None,
        "docx_assoc": info.get("docx_assoc") or "",
    }
    if src.suffix.lower() in NEED_BRIDGE:
        try:
            work, office_meta = convert_to_ooxml(src, info)
        except Exception as exc:
            die(str(exc), office=info)
    markitdown(work, dest)
    if work != src and os.environ.get("DOC2MD_KEEP_OOXML") != "1":
        try:
            work.unlink(missing_ok=True)
        except TypeError:
            try:
                work.unlink()
            except OSError:
                pass
        except OSError:
            pass
    return {"engine": "markitdown", "mode": "direct", "timeout_hint": "short", "office": office_meta}


def win_unc_to_posix(s: str) -> str | None:
    t = s.replace("/", "\\")
    parts = [p for p in t.split("\\") if p]
    if len(parts) >= 3 and parts[0].lower() in {"wsl.localhost", "wsl$"}:
        return "/" + "/".join(parts[2:])
    return None


def posix_or_str(path: Path, override: str | None = None) -> str:
    if override:
        return override
    s = str(path)
    if s.startswith("/"):
        return s
    converted = win_unc_to_posix(s)
    return converted or s


def reject_derivative(src: Path) -> None:
    name = src.name
    if any(name.endswith(suffix) for suffix in DERIVATIVE_SUFFIXES):
        die("refusing to convert a derivative file; pass the original document", input=str(src))


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument(
        "--mode",
        choices=("auto", "skip-text", "force-ocr"),
        default="auto",
        help="auto/skip-text = extract text first; force-ocr = rasterize and OCR",
    )
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--detect-office", action="store_true", help="print Office/WPS detection JSON and exit")
    args = parser.parse_args()

    if args.detect_office:
        from office_bridge import detect as detect_office

        print(json.dumps({"ok": True, "office": detect_office()}, ensure_ascii=False), flush=True)
        return

    if args.input is None:
        die("input file required")
    src = args.input.expanduser().resolve()
    if not src.is_file():
        die(f"input not found: {args.input}")
    reject_derivative(src)

    dest = args.output.expanduser().resolve() if args.output else src.with_name(f"{src.stem}{DEFAULT_SUFFIX}")
    ext = src.suffix.lower()
    mode = "skip-text" if args.mode == "auto" else args.mode
    posix_in = os.environ.get("DOC2MD_POSIX_INPUT") or None
    posix_out = os.environ.get("DOC2MD_POSIX_OUTPUT") or None
    if posix_in and not posix_out and args.output is None:
        posix_out = str(Path(posix_in).with_name(dest.name))

    if ext in IMAGE_EXT:
        meta = convert_image(src, dest)
    elif ext == ".pdf":
        meta = convert_pdf(src, dest, mode)
    else:
        meta = convert_office_or_other(src, dest)

    text = dest.read_text(encoding="utf-8", errors="replace")
    print(
        json.dumps(
            {
                "ok": True,
                "input": posix_or_str(src, posix_in),
                "markdown": posix_or_str(dest, posix_out),
                "input_native": str(src),
                "markdown_native": str(dest),
                "chars": len(text),
                "size_bytes": src.stat().st_size,
                "python": sys.executable,
                **meta,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        die(str(exc))
