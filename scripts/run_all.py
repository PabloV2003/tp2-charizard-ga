"""Regenera TODA la evidencia en orden: experimentos, comparaciones, graficos, legalidad, notebook,
validacion y paquete ZIP.

Uso:
    python scripts/run_all.py                 # usa el dataset local de data/
    python scripts/run_all.py --with-data     # ademas re-prepara el dataset desde los commits fijados (requiere internet)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step(name: str, args: list[str], optional: bool = False):
    print(f"\n=== {name} ===", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, *args], cwd=ROOT)
    print(f"--- {name}: codigo {proc.returncode} en {time.perf_counter() - t0:.1f} s", flush=True)
    if proc.returncode != 0 and not optional:
        raise SystemExit(f"Fallo el paso: {name}")
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-data", action="store_true")
    a = parser.parse_args()
    exps = json.loads((ROOT / "config" / "experiments.json").read_text(encoding="utf-8"))
    n_runs = len(exps["configs"]) * len(exps["seeds"])
    if a.with_data:
        step("Preparacion de datos", ["scripts/prepare_data.py"])
    step(f"Experimentos ({n_runs} corridas)", ["scripts/run_experiments.py"])
    step("Comparacion con otros metodos", ["scripts/run_baselines.py"])
    step("Graficos", ["scripts/make_figures.py"])
    if shutil.which("node"):
        step("Legalidad con Showdown (opcional)", ["scripts/validate_legality_showdown.py"], optional=True)
    else:
        print("\nNode.js no disponible: se omite la verificacion opcional de legalidad (se conservan sus resultados previos).")
    step("Notebook", ["scripts/build_notebook.py"])
    step("Validacion", ["scripts/run_validation.py"])
    step("Paquete ZIP", ["scripts/make_package.py"])


if __name__ == "__main__":
    main()
