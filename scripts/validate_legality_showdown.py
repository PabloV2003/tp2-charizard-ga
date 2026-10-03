"""Verificacion EXTERNA y OPCIONAL de coexistencia: valida los movesets resultantes con el validador de equipos
de Pokemon Showdown (formato "[Gen 9] Anything Goes", que aplica la regla 'Obtainable').

Por que: el catalogo solo garantiza que cada movimiento, por separado, pertenece al learnset de Escarlata/Purpura.
El validador comprueba que los CUATRO movimientos puedan coexistir en un mismo Charizard bajo las reglas de Gen 9
(por ejemplo, incompatibilidades entre movimientos de evento o de huevo).

Requisitos: Node.js y git. Con --setup se descarga Showdown en el commit fijado en config/data_sources.json
(carpeta .cache/, excluida del paquete) y se instalan sus dependencias con npm.

Uso:
    python scripts/validate_legality_showdown.py --setup   # primera vez (descarga ~100 MB)
    python scripts/validate_legality_showdown.py

Nota: el validador exige al menos 1 EV para no advertir "0 EVs"; se agrega "EVs: 1 HP" solo para pasar ese
control de formato. El modelo del TP no usa EV, objetos ni naturalezas.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from charizard_ga.data import load_catalog  # noqa: E402
from charizard_ga.io_utils import write_json, write_rows_csv  # noqa: E402
from charizard_ga.paths import CONFIG_DIR, RESULTS_DIR, ROOT  # noqa: E402

FORMAT = "gen9anythinggoes"
SD_DIR = ROOT / ".cache" / "pokemon-showdown"


def run(cmd, cwd=None, stdin=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8",
                          shell=(sys.platform == "win32" and cmd[0] == "npm"))


def setup(commit: str):
    if (SD_DIR / "package.json").exists():
        print("Showdown ya descargado en", SD_DIR)
    else:
        SD_DIR.mkdir(parents=True, exist_ok=True)
        for cmd in (["git", "init", "-q"], ["git", "remote", "add", "origin", "https://github.com/smogon/pokemon-showdown.git"],
                    ["git", "fetch", "-q", "--depth", "1", "origin", commit], ["git", "checkout", "-q", "FETCH_HEAD"]):
            r = run(cmd, cwd=SD_DIR)
            if r.returncode != 0:
                raise SystemExit(f"Fallo {' '.join(cmd)}: {r.stderr}")
    r = run(["npm", "install", "--no-audit", "--no-fund"], cwd=SD_DIR)
    if r.returncode != 0:
        raise SystemExit("Fallo npm install: " + r.stderr[-2000:])


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def collect_movesets(catalog) -> list[tuple[str, tuple]]:
    """Movesets a validar: mejores de todas las corridas, optimos exactos (con empates), optimos del
    subconjunto conservador, heuristicas y el ejemplo numerico del informe."""
    found: dict[tuple, list[str]] = {}

    def add(origin, slugs_text):
        key = tuple(sorted(catalog.by_slug(s) for s in slugs_text.split("|")))
        found.setdefault(key, [])
        if origin not in found[key]:
            found[key].append(origin)

    for r in read_csv(RESULTS_DIR / "summary_runs.csv"):
        add(f"AG {r['config_id']}", r["moveset_slugs"])
    base = RESULTS_DIR / "baselines"
    for r in read_csv(base / "exhaustive_optimum.csv"):
        for ms in r["movesets_optimos"].split(" || "):
            add(f"optimo {r['perfil']}", ms)
    for r in read_csv(base / "conservative_optimum.csv"):
        for ms in r["movesets_optimos"].split(" || "):
            add(f"optimo conservador {r['perfil']}", ms)
    for r in read_csv(base / "greedy.csv"):
        add(f"{r['metodo']} {r['perfil']}", r["mejor_moveset"])
    add("ejemplo numérico", "flamethrower|air-slash|dragon-pulse|solar-beam")
    return [(", ".join(v), k) for k, v in found.items()]


def team_text(names: list[str]) -> str:
    return "Charizard\nAbility: Blaze\nEVs: 1 HP\n" + "".join(f"- {n}\n" for n in names)


def validate(names: list[str]) -> tuple[bool, str]:
    r = run(["node", "pokemon-showdown", "validate-team", FORMAT], cwd=SD_DIR, stdin=team_text(names))
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--setup", action="store_true", help="descarga Showdown (commit fijado) e instala dependencias")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    commit = json.loads((CONFIG_DIR / "data_sources.json").read_text(encoding="utf-8"))["showdown"]["commit"]
    if not shutil.which("node"):
        raise SystemExit("Node.js no esta instalado: esta verificacion externa es opcional y no se puede ejecutar.")
    if args.setup or not (SD_DIR / "node_modules").exists():
        setup(commit)
    head = run(["git", "rev-parse", "HEAD"], cwd=SD_DIR).stdout.strip()
    if head != commit:
        raise SystemExit(f"Showdown en {SD_DIR} esta en {head}, se esperaba {commit}")

    catalog = load_catalog()
    rows = []
    for origin, key in collect_movesets(catalog):
        names = [catalog.moves[m].nombre_en for m in key]
        ok, msg = validate(names)
        rows.append({"tipo_caso": "moveset_resultante", "origen": origin, "moveset": "|".join(catalog.moves[m].slug for m in key),
                     "movimientos_en": " / ".join(names), "valido_showdown": ok, "mensaje": msg})
        print(f"{'VALIDO  ' if ok else 'INVALIDO'} {' / '.join(names)}  <- {origin}" + ("" if ok else f"  [{msg}]"))
    # Controles: comprueban que el validador realmente rechaza lo ilegal.
    controls = [("control_negativo", "Thunderbolt no está en el learnset de Charizard", ["Thunderbolt", "Solar Beam", "Earthquake", "Focus Punch"]),
                ("control_negativo", "Movimiento repetido", ["Earthquake", "Earthquake", "Fly", "Focus Punch"])]
    for kind, desc, names in controls:
        ok, msg = validate(names)
        rows.append({"tipo_caso": kind, "origen": desc, "moveset": "", "movimientos_en": " / ".join(names),
                     "valido_showdown": ok, "mensaje": msg})
        print(f"control: {desc}: {'VALIDO (inesperado)' if ok else 'rechazado (esperado)'} [{msg}]")

    write_rows_csv(RESULTS_DIR / "legality_showdown.csv", rows, list(rows[0].keys()))
    node_v = run(["node", "--version"]).stdout.strip()
    resultantes = [r for r in rows if r["tipo_caso"] == "moveset_resultante"]
    write_json(RESULTS_DIR / "legality_showdown.json", {
        "fecha_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "showdown_commit": head, "formato": FORMAT, "regla": "Standard AG -> Obtainable", "node": node_v,
        "movesets_validados": len(resultantes), "movesets_validos": sum(r["valido_showdown"] for r in resultantes),
        "controles_rechazados": sum(not r["valido_showdown"] for r in rows if r["tipo_caso"] == "control_negativo"),
        "controles": len(controls),
        "nota": "EVs: 1 HP se agrega solo para evitar la advertencia de 0 EVs del validador; no forma parte del modelo.",
    })
    print(f"\n{sum(r['valido_showdown'] for r in resultantes)}/{len(resultantes)} movesets resultantes validos en {FORMAT}")


if __name__ == "__main__":
    main()
