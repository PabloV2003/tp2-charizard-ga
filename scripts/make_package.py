"""Crea dist/TP2_Grupo6_Charizard_entrega_final.zip con todos los entregables.

Excluye entornos virtuales, caches, descargas temporales, el propio dist/ y archivos de git.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "TP2_Grupo6_Charizard_entrega_final.zip"
EXCLUDED_DIRS = {".venv", "venv", ".cache", "cache", "__pycache__", ".pytest_cache", ".ipynb_checkpoints", "dist", ".git", "demo"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {"pytest_report.xml", ".DS_Store", "Thumbs.db"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in rel.parts[:-1]):
        return False
    if path.suffix in EXCLUDED_SUFFIXES or path.name in EXCLUDED_NAMES or path.name.startswith("~$"):
        return False
    return path.is_file()


def main():
    OUT.parent.mkdir(exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if included(p))
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            zf.write(p, Path("entrega_final") / p.relative_to(ROOT))
    size = OUT.stat().st_size / 1e6
    print(f"{OUT.relative_to(ROOT)}: {len(files)} archivos, {size:.1f} MB")


if __name__ == "__main__":
    main()
