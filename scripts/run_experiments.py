"""Lote completo de experimentos: 15 configuraciones x 10 semillas (42..51).

Configuraciones (config/experiments.json; todas con aptitud F2 y cruza de conjuntos salvo lo indicado):
    R1..R5    -> cinco perfiles de pesos con los mismos parametros del AG (corridas principales: semilla 42).
    ORIG-R1   -> version original para comparar: aptitud F1 y cruza binomial aleatoria, pesos base.
    OP-UNIF   -> pesos base, cruza binomial aleatoria (uniforme) con reparacion.
    OP-1P     -> pesos base, cruza simple (un punto) con reparacion.
    OP-RUL    -> pesos base, seleccion por ruleta.
    OP-RANK   -> pesos base, seleccion por ranking lineal.
    OP-CNE    -> pesos base, seleccion por control sobre numero esperado.
    OP-MUT20  -> pesos base, mutacion 0.20.
    OP-MUTAD  -> pesos base, mutacion adaptativa por convergencia.
    OP-ESTANC -> pesos base, paro por estancamiento.
    OP-POB20  -> pesos base, poblacion 20 y 30 generaciones.

Salidas:
    results/runs/<config>/seed_<s>_log.csv      log por generacion (generacion 0 incluida)
    results/runs/<config>/seed_<s>_summary.json resumen y mejor solucion de la corrida
    results/summary_runs.csv                    una fila por corrida
    results/summary_configs.csv                 media, desvio y rango por configuracion
    results/parameters.json                     parametros completos para reconstruir las corridas
    results/environment.json                    entorno de ejecucion
"""
from __future__ import annotations

import argparse
import datetime as dt
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charizard_ga.config import load_experiments, load_quality_criterion  # noqa: E402
from charizard_ga.data import load_catalog, load_metadata  # noqa: E402
from charizard_ga.experiments import run_and_save  # noqa: E402
from charizard_ga.fitness import DEFAULT_FITNESS, FITNESS_VERSIONS  # noqa: E402
from charizard_ga.io_utils import environment_info, write_json, write_rows_csv  # noqa: E402
from charizard_ga.paths import RESULTS_DIR  # noqa: E402

RUN_FIELDS = [
    "config_id", "grupo", "perfil", "perfil_nombre", "replica", "semilla", "corrida_principal", "fitness_version",
    "mejor_aptitud", "aptitud_perfil_base", "generacion_encontrada", "generaciones_ejecutadas", "moveset_slugs", "moveset_es",
    "C", "P", "A", "S", "D", "n_tipos_cubiertos", "tipos_cubiertos", "tipos_no_cubiertos",
    "candidatos_generados", "evaluaciones_solicitadas", "evaluaciones_efectivas", "tiempo_segundos",
    "distintas_poblacion_final", "media_poblacion_final", "hijos_reparados_total", "invalidos_registrados",
]


def flatten(summary: dict) -> dict:
    best = summary["mejor_solucion"]
    return {
        "config_id": summary["config_id"], "grupo": summary["grupo"], "perfil": summary["perfil"],
        "perfil_nombre": summary["perfil_nombre"], "replica": summary["replica"], "semilla": summary["semilla"],
        "corrida_principal": summary["corrida_principal"], "fitness_version": summary["fitness_version"],
        "mejor_aptitud": best["aptitud"],
        "aptitud_perfil_base": best["aptitud_perfil_base"], "generacion_encontrada": best["generacion_encontrada"],
        "generaciones_ejecutadas": summary["generaciones_ejecutadas"],
        "moveset_slugs": "|".join(m["slug"] for m in best["movimientos"]),
        "moveset_es": " | ".join(m["nombre_es"] for m in best["movimientos"]),
        **best["componentes"], "n_tipos_cubiertos": best["n_tipos_cubiertos"],
        "tipos_cubiertos": "|".join(best["tipos_cubiertos"]), "tipos_no_cubiertos": "|".join(best["tipos_no_cubiertos"]),
        "candidatos_generados": summary["candidatos_generados"], "evaluaciones_solicitadas": summary["evaluaciones_solicitadas"],
        "evaluaciones_efectivas": summary["evaluaciones_efectivas"], "tiempo_segundos": summary["tiempo_segundos"],
        "distintas_poblacion_final": summary["poblacion_final"]["combinaciones_distintas"],
        "media_poblacion_final": summary["poblacion_final"]["aptitud_media"],
        "hijos_reparados_total": summary["total_hijos_reparados"],
        "invalidos_registrados": summary["total_individuos_invalidos_registrados"],
    }


def aggregate(rows: list[dict], configs) -> list[dict]:
    out = []
    for exp in configs:
        rs = [r for r in rows if r["config_id"] == exp.config_id]
        if not rs:
            continue
        vals = [r["mejor_aptitud"] for r in rs]
        base_vals = [r["aptitud_perfil_base"] for r in rs]
        gens = [r["generacion_encontrada"] for r in rs]
        movesets = Counter(r["moveset_slugs"] for r in rs)
        modal, modal_n = movesets.most_common(1)[0]
        out.append({
            "config_id": exp.config_id, "grupo": exp.grupo, "perfil": exp.profile, "descripcion": exp.descripcion,
            "n_replicas": len(rs),
            "aptitud_media": statistics.fmean(vals), "aptitud_desvio": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "aptitud_min": min(vals), "aptitud_max": max(vals),
            "aptitud_base_media": statistics.fmean(base_vals),
            "aptitud_base_desvio": statistics.stdev(base_vals) if len(base_vals) > 1 else 0.0,
            "generacion_encontrada_media": statistics.fmean(gens), "generacion_encontrada_min": min(gens),
            "generacion_encontrada_max": max(gens),
            "evaluaciones_efectivas_media": statistics.fmean(r["evaluaciones_efectivas"] for r in rs),
            "evaluaciones_solicitadas_media": statistics.fmean(r["evaluaciones_solicitadas"] for r in rs),
            "tiempo_medio_segundos": statistics.fmean(r["tiempo_segundos"] for r in rs),
            "movesets_distintos": len(movesets), "moveset_modal": modal, "frecuencia_modal": modal_n,
            "distintas_poblacion_final_media": statistics.fmean(r["distintas_poblacion_final"] for r in rs),
        })
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", nargs="*", help="subconjunto de configuraciones (por defecto, todas)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    catalog = load_catalog()
    meta = load_metadata()
    if meta["dataset_version"] != catalog.dataset_version:
        raise SystemExit("El hash del dataset no coincide con data/metadata.json; regenere los datos.")
    exps = load_experiments()
    base_weights = exps["profiles"][exps["base_profile"]]
    configs = [c for c in exps["configs"] if not args.configs or c.config_id in args.configs]
    runs_dir = RESULTS_DIR / "runs"

    write_json(RESULTS_DIR / "parameters.json", {
        "generado_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "dataset_version": catalog.dataset_version, "fitness_version_por_defecto": DEFAULT_FITNESS,
        "fitness_versiones": FITNESS_VERSIONS,
        "catalogo_M": catalog.M, "potencia_maxima_normalizacion_F1": catalog.power_max,
        "potencia_efectiva_maxima_normalizacion_F2": catalog.power_eff_max,
        "estadisticas_base_charizard": catalog.base_stats,
        "semillas": exps["seeds"], "semilla_principal": exps["main_seed"], "perfil_base": exps["base_profile"],
        "alcance_probabilidades": exps["raw"]["alcance_probabilidades"],
        "criterio_calidad": load_quality_criterion(),
        "configuraciones": [{
            "config_id": c.config_id, "grupo": c.grupo, "perfil": c.profile, "perfil_nombre": c.profile_name,
            "descripcion": c.descripcion, "pesos": c.weights.to_dict(), "parametros_ag": c.ga.to_dict(),
            "overrides_respecto_base": c.overrides} for c in configs],
    })
    write_json(RESULTS_DIR / "environment.json", environment_info())

    rows = []
    for exp in configs:
        for replica, seed in enumerate(exps["seeds"], start=1):
            is_main = exp.grupo == "principal" and seed == exps["main_seed"]
            summary = run_and_save(exp, seed, catalog, base_weights, runs_dir, is_main=is_main, replica=replica)
            rows.append(flatten(summary))
            best = summary["mejor_solucion"]
            print(f"{exp.config_id:9s} seed {seed}: F={best['aptitud']:.4f} gen={best['generacion_encontrada']:3d} "
                  f"[{rows[-1]['moveset_slugs']}] efectivas={summary['evaluaciones_efectivas']} t={summary['tiempo_segundos']:.2f}s")

    write_rows_csv(RESULTS_DIR / "summary_runs.csv", rows, RUN_FIELDS)
    agg = aggregate(rows, configs)
    write_rows_csv(RESULTS_DIR / "summary_configs.csv", agg, list(agg[0].keys()))
    print(f"\n{len(rows)} corridas guardadas en {runs_dir}")


if __name__ == "__main__":
    main()
