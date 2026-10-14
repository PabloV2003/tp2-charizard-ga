"""Validacion integral de la entrega y registro en docs/registro_validacion.md.

Verifica:
  1. Suite de pruebas (pytest).
  2. Reproducibilidad: las 5 corridas principales (semilla 42) se reejecutan y sus logs coinciden con los guardados.
  3. Ejecucion desde cero: se copia el proyecto (sin resultados ni entorno) a una carpeta temporal y se ejecuta la
     demostracion por consola con el dataset local y rutas relativas.
  4. Notebook ejecutado sin errores y con salidas.
  5. Graficos de todas las corridas y de los analisis presentes.
  6. Legalidad conjunta de los movesets con Showdown, si se ejecuto la verificacion opcional.

Uso:  python scripts/run_validation.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from charizard_ga.config import load_experiments  # noqa: E402
from charizard_ga.data import load_catalog  # noqa: E402
from charizard_ga.experiments import run_and_save  # noqa: E402
from charizard_ga.io_utils import environment_info  # noqa: E402

RESULTS = ROOT / "results"


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def run_pytest() -> dict:
    xml_path = RESULTS / "pytest_report.xml"
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml_path}"],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    suite = ET.parse(xml_path).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    total = int(suite.get("tests"))
    failed = int(suite.get("failures")) + int(suite.get("errors"))
    skipped = int(suite.get("skipped"))
    cases = [f"{c.get('classname')}::{c.get('name')}" for c in suite.iter("testcase")]
    return {"total": total, "passed": total - failed - skipped, "failed": failed, "skipped": skipped,
            "salida": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "", "casos": cases}


def check_reproducibility() -> dict:
    catalog = load_catalog()
    exps = load_experiments()
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for exp in [c for c in exps["configs"] if c.grupo == "principal"]:
            new = run_and_save(exp, exps["main_seed"], catalog, exps["profiles"]["R1"], Path(tmp), is_main=True, replica=1)
            out[exp.config_id] = read_csv(new["_log_path"]) == read_csv(RESULTS / "runs" / exp.config_id / f"seed_{exps['main_seed']}_log.csv")
    return out


def check_fresh_copy() -> dict:
    """Copia minima del proyecto (codigo + config + data) y ejecucion de la demo desde esa copia."""
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "proyecto"
        for name in ("src", "scripts", "config", "data"):
            shutil.copytree(ROOT / name, dst / name, ignore=shutil.ignore_patterns("cache", "__pycache__"))
        proc = subprocess.run([sys.executable, "scripts/run_ga.py", "--config", "R1", "--seed", "42"], cwd=dst,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        demo_log = dst / "results" / "demo" / "R1" / "seed_42_log.csv"
        same = demo_log.exists() and read_csv(demo_log) == read_csv(RESULTS / "runs" / "R1" / "seed_42_log.csv")
        return {"codigo_salida": proc.returncode, "log_identico_al_guardado": same,
                "sin_cache_de_descargas": not (dst / "data" / "cache").exists(),
                # La ruta temporal se reemplaza por un marcador para no publicar rutas locales del equipo.
                "ultima_linea": (proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-300:])
                .replace(str(dst), "<copia_temporal>")}


def check_notebook() -> dict:
    import nbformat
    nb = nbformat.read(ROOT / "notebooks" / "tp2_charizard.ipynb", as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    errors = sum(1 for c in code for o in c.get("outputs", []) if o.get("output_type") == "error")
    executed = all(c.get("execution_count") for c in code)
    counts = [c.get("execution_count") for c in code]
    return {"celdas_codigo": len(code), "todas_ejecutadas": executed, "orden_secuencial": counts == list(range(1, len(code) + 1)),
            "errores": errors}


def check_figures() -> dict:
    runs = read_csv(RESULTS / "summary_runs.csv")
    missing = [f"{r['config_id']}_seed{r['semilla']}" for r in runs
               if not (ROOT / "figures" / "runs" / f"{r['config_id']}_seed{r['semilla']}.png").exists()]
    analysis = ["fig_tabla_tipos.png", "fig_variabilidad.png", "fig_operadores.png", "fig_seleccion.png",
                "fig_componentes_perfiles.png", "fig_ag_vs_aleatoria.png", "fig_distribucion_exhaustiva.png"]
    missing += [a for a in analysis if not (ROOT / "figures" / a).exists()]
    return {"graficos_corridas": len(runs), "graficos_analisis": len(analysis), "faltantes": missing}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("1/5 pytest...")
    pytest_res = run_pytest()
    print("   ", pytest_res["salida"])
    print("2/5 reproducibilidad de las corridas principales...")
    repro = check_reproducibility()
    print("   ", repro)
    print("3/5 ejecucion desde una copia limpia...")
    fresh = check_fresh_copy()
    print("   ", fresh)
    print("4/5 notebook...")
    nb = check_notebook()
    print("   ", nb)
    print("5/5 graficos y legalidad...")
    figs = check_figures()
    legal = json.loads((RESULTS / "legality_showdown.json").read_text(encoding="utf-8")) if (RESULTS / "legality_showdown.json").exists() else None

    ok = (pytest_res["failed"] == 0 and all(repro.values()) and fresh["codigo_salida"] == 0 and fresh["log_identico_al_guardado"]
          and nb["errores"] == 0 and nb["todas_ejecutadas"] and not figs["faltantes"])
    summary = {"fecha_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "todo_ok": ok,
               "pytest": {k: v for k, v in pytest_res.items() if k != "casos"}, "reproducibilidad_corridas_principales": repro,
               "copia_limpia": fresh, "notebook": nb, "graficos": figs, "legalidad_showdown": legal,
               "entorno": environment_info()}
    (RESULTS / "validation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_registry(summary, pytest_res["casos"])
    print("TODO OK" if ok else "HAY VERIFICACIONES FALLIDAS", "-> docs/registro_validacion.md")
    return 0 if ok else 1


def write_registry(s: dict, cases: list[str]):
    yes = lambda b: "sí" if b else "NO"  # noqa: E731
    pt = s["pytest"]
    lines = [
        "# Registro de validación", "",
        f"Generado por `scripts/run_validation.py` el {s['fecha_utc']} (UTC). Resultado global: "
        f"**{'todas las verificaciones aprobadas' if s['todo_ok'] else 'hay verificaciones fallidas'}**.", "",
        f"Entorno: Python {s['entorno']['python']}, DEAP {s['entorno']['deap']}, {s['entorno']['sistema']}.", "",
        "## 1. Pruebas automatizadas (pytest)", "",
        f"- Total {pt['total']}: {pt['passed']} aprobadas, {pt['failed']} fallidas, {pt['skipped']} omitidas. Salida: `{pt['salida']}`.",
        "- Casos:", ""] + [f"  - `{c}`" for c in cases] + ["",
        "Cobertura de los requisitos de verificación:", "",
        "| Verificación pedida | Prueba |", "|---|---|",
        "| Fórmulas C/P/A/S/D y F (F2 y F1) contra un caso calculado independientemente | `test_fitness::test_example_components_hand_computed`, `test_example_fitness_base_profile` |",
        "| Potencia efectiva (F2) contra valores calculados a mano y mecánicas leídas de Showdown | `test_fitness::test_effective_power_hand_computed`, `test_data::test_mechanics_for_effective_power` |",
        "| F2 como versión por defecto; F1 solo como referencia, con óptimo y caché propios | `test_fitness::test_default_version_is_f2`, `test_cache_is_isolated_per_version`, `test_baselines::test_exhaustive_optimum_f1_vs_f2` |",
        "| Aptitud 0 ante longitud incorrecta, repetidos o IDs no permitidos | `test_fitness::test_invalid_individuals_get_zero` |",
        "| Invariancia frente a permutaciones | `test_fitness::test_permutation_invariance` |",
        "| Orientación y valores de la tabla de tipos, incluidas inmunidades | `test_data::test_type_chart_*`, `test_super_effective_sets` |",
        "| Inicialización, cruza/reparación y mutación coherentes con las restricciones | `test_operators::*` |",
        "| Cruza de conjuntos: conserva los genes comunes y nunca genera repetidos | `test_operators::test_set_crossover_keeps_shared_genes_and_never_repeats`, `test_positional_crossover_can_lose_shared_genes` |",
        "| Selección por ranking y por control sobre número esperado; mutación adaptativa | `test_operators::test_ranking_selection_depends_on_order_not_on_values`, `test_expected_count_selection_follows_the_class_example`, `test_adaptive_mutation_rises_when_population_converges` |",
        "| Tamaño constante, élites conservadas, mejor acumulada coherente (con cada variante de selección, cruza y mutación) | `test_ga::test_population_and_best_invariants` |",
        "| Paro por estancamiento | `test_ga::test_stagnation_stops_after_patience_without_improvement` |",
        "| Misma semilla y configuración => mismos resultados (sin tiempos) | `test_ga::test_same_seed_same_results_excluding_time`, `test_results_consistency::test_saved_main_run_is_reproducible` |",
        "| Gráficos, tablas y resúmenes coinciden con los logs | `test_results_consistency::*` |",
        "| Reinicialización correcta de DEAP entre corridas | `test_ga::test_deap_types_can_be_recreated_without_warnings` |",
        "| Caché aislada por pesos/dataset | `test_fitness::test_cache_is_isolated_per_weights` |", "",
        "## 2. Reproducibilidad de las corridas principales (semilla 42)", ""]
    lines += [f"- {k}: log reproducido idéntico = {yes(v)}" for k, v in s["reproducibilidad_corridas_principales"].items()]
    f = s["copia_limpia"]
    lines += ["", "## 3. Ejecución desde cero con el dataset local y rutas relativas", "",
              "Se copiaron `src/`, `scripts/`, `config/` y `data/` (sin la caché de descargas) a una carpeta temporal y se ejecutó "
              "`python scripts/run_ga.py --config R1 --seed 42` desde allí.", "",
              f"- Código de salida: {f['codigo_salida']}; log idéntico al guardado: {yes(f['log_identico_al_guardado'])}; "
              f"sin caché de descargas: {yes(f['sin_cache_de_descargas'])}.", f"- Última línea de la salida: `{f['ultima_linea']}`", "",
              "## 4. Notebook", "",
              f"- `notebooks/tp2_charizard.ipynb`: {s['notebook']['celdas_codigo']} celdas de código, ejecutadas en orden "
              f"{yes(s['notebook']['orden_secuencial'])}, errores: {s['notebook']['errores']}. Se regenera y ejecuta en un kernel "
              "nuevo con `scripts/build_notebook.py` (no depende de estado oculto).", "",
              "## 5. Gráficos", "",
              f"- {s['graficos']['graficos_corridas']} gráficos de corridas y {s['graficos']['graficos_analisis']} de análisis; "
              f"faltantes: {s['graficos']['faltantes'] or 'ninguno'}. Todos se generan desde los CSV con `scripts/make_figures.py`.", ""]
    section = 6
    if s["legalidad_showdown"]:
        lg = s["legalidad_showdown"]
        lines += [f"## {section}. Legalidad conjunta de los movesets (verificación externa opcional)", "",
                  f"- Validador de Pokémon Showdown, formato `{lg['formato']}` ({lg['regla']}), commit `{lg['showdown_commit'][:12]}`: "
                  f"{lg['movesets_validos']}/{lg['movesets_validados']} movesets resultantes válidos; "
                  f"{lg['controles_rechazados']}/{lg['controles']} controles negativos rechazados. Detalle en "
                  "`results/legality_showdown.csv`.", ""]
        section += 1
    lines += [f"## {section}. Errores de desarrollo detectados y corregidos", "",
              "- Lector de banderas de Showdown: no marcaba Vuelo/Excavar como movimientos con carga (banderas en varias líneas).",
              "- Diferencia de 2e-16 entre el óptimo calculado con numpy y la aptitud del AG: el óptimo se recalcula con la misma rutina.",
              ""]
    (ROOT / "docs" / "registro_validacion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
