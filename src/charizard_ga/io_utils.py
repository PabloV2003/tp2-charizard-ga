"""Escritura de evidencias: logs CSV por generacion y resumenes JSON por corrida.

Los valores numericos se guardan con precision completa (repr de float); el redondeo se hace
solo al presentar resultados (tablas del informe y graficos).
"""
from __future__ import annotations

import csv
import json
import os
import platform
import sys
from pathlib import Path


def write_rows_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k, "")) for k in fieldnames})


def _fmt(value):
    # repr conserva todos los digitos significativos de un float (ida y vuelta exacta).
    if isinstance(value, float):
        return repr(value)
    return value


def write_json(path: Path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")


def _json_default(obj):
    if isinstance(obj, tuple):
        return list(obj)
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"No serializable: {type(obj)}")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def environment_info() -> dict:
    """Entorno de ejecucion (para reportar tiempos con contexto)."""
    from importlib.metadata import PackageNotFoundError, version

    def pkg(name):
        try:
            return version(name)
        except PackageNotFoundError:  # pragma: no cover
            return None

    return {
        "python": sys.version.split()[0],
        "implementacion": platform.python_implementation(),
        "sistema": platform.platform(),
        "procesador": platform.processor(),
        "nucleos_logicos": os.cpu_count(),
        "deap": pkg("deap"),
        "numpy": pkg("numpy"),
        "pandas": pkg("pandas"),
        "matplotlib": pkg("matplotlib"),
        "python_docx": pkg("python-docx"),
        "pytest": pkg("pytest"),
        "nbconvert": pkg("nbconvert"),
    }
