"""Runtime discovery for optional system executables used by ingestion."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

__all__ = [
    "find_libreoffice",
    "find_tesseract",
    "tesseract_language",
    "runtime_diagnostics",
]


def _first_executable(candidates: list[str]) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)
    return None


def find_libreoffice() -> str | None:
    """Return a usable LibreOffice/soffice executable, including macOS app paths."""
    return _first_executable([
        "libreoffice",
        "soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/opt/homebrew/bin/libreoffice",
        "/opt/homebrew/bin/soffice",
        "/usr/local/bin/libreoffice",
        "/usr/local/bin/soffice",
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
    ])


def find_tesseract() -> str | None:
    """Return a usable Tesseract executable from PATH or common macOS locations."""
    return _first_executable([
        "tesseract",
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
    ])


def _tesseract_languages(executable: str) -> set[str]:
    try:
        result = subprocess.run(
            [executable, "--list-langs"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=True,
        )
    except Exception:
        return set()
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {line for line in lines if not line.lower().startswith("list of available")}


def tesseract_language(executable: str) -> str | None:
    """Choose the best installed OCR language without requiring one exact package."""
    languages = _tesseract_languages(executable)
    # Prefer Polish OCR for Polish hospital documents.  The generic Latin model
    # is useful as a fallback, but it is materially worse at Polish diacritics
    # and can also change digit segmentation in scanned salary tables.
    if "pol" in languages:
        return "pol"
    if "Latin" in languages:
        return "Latin"
    if "eng" in languages:
        return "eng"
    return next(iter(sorted(languages)), None)


def runtime_diagnostics() -> list[tuple[str, str, str]]:
    """Return dependency name, status, and resolved runtime detail."""
    office = find_libreoffice()
    tess = find_tesseract()
    tess_lang = tesseract_language(tess) if tess else None
    return [
        (
            "LibreOffice (.xls)",
            "OK" if office else "MISSING",
            office or "install LibreOffice; on macOS: brew install --cask libreoffice",
        ),
        (
            "Tesseract OCR (scanned PDF)",
            "OK" if tess and tess_lang else "MISSING",
            f"{tess} [lang={tess_lang}]" if tess and tess_lang else
            "install Tesseract; on macOS: brew install tesseract (optionally tesseract-lang)",
        ),
    ]
