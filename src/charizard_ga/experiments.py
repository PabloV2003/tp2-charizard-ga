"""Ejecucion de una corrida configurada y guardado de sus evidencias (log CSV + resumen JSON).

Lo usan tanto la demostracion por consola (scripts/run_ga.py) como el lote de experimentos
(scripts/run_experiments.py), para que ambos produzcan exactamente los mismos archivos.
"""
from __future__ import annotations

from pathlib import Path

from .config import ExperimentConfig
from .data import Catalog
from .fitness import FITNESS_VERSIONS, Weights
from .ga import RunResult, describe_solution, run_ga
from .io_utils import write_json, write_rows_csv

LOG_FIELDS = [
    "generacion", "tam_poblacion", "prob_mutacion", "aptitud_min", "aptitud_media", "aptitud_max", "aptitud_desvio",
    "mejor_acumulada", "generacion_mejor_acumulada", "combinaciones_distintas", "individuos_invalidos",
    "evaluaciones_solicitadas", "evaluaciones_efectivas", "evaluaciones_solicitadas_acum",
    "evaluaciones_efectivas_acum", "cruzas", "mutaciones", "hijos_reparados", "genes_reparados",
    "mejor_generacion_moveset", "mejor_acumulada_moveset",
]


def run_paths(out_dir: Path, config_id: str, seed: int) -> tuple[Path, Path]:
    base = Path(out_dir) / config_id
    return base / f"seed_{seed}_log.csv", base / f"seed_{seed}_summary.json"


def build_summary(exp: ExperimentConfig, result: RunResult, catalog: Catalog, base_weights: Weights,
                  is_main: bool) -> dict:
    """Resumen completo de una corrida: configuracion, semilla, versiones y mejor solucion decodificada."""
    sol = describe_solution(result.best_moveset, catalog, exp.weights, base_weights, result.fitness_version)
    last = result.log[-1]
    return {
        "config_id": exp.config_id,
        "grupo": exp.grupo,
        "perfil": exp.profile,
        "perfil_nombre": exp.profile_name,
        "descripcion": exp.descripcion,
        "replica": None,  # se completa en el lote (1..10)
        "semilla": result.seed,
        "corrida_principal": is_main,
        "parametros_ag": result.ga,
        "overrides_respecto_base": exp.overrides,
        "pesos": result.weights,
        "dataset_version": result.dataset_version,
        "fitness_version": result.fitness_version,
        "fitness_descripcion": FITNESS_VERSIONS[result.fitness_version],
        "mejor_solucion": {
            "moveset_ids": list(result.best_moveset),
            "generacion_encontrada": result.best_generation,
            **sol,
        },
        "generaciones_ejecutadas": result.generations_executed,
        "filas_log": len(result.log),
        "motivo_paro": result.stop_reason,
        "tiempo_segundos": result.elapsed_seconds,
        "candidatos_generados": result.candidates_generated,
        "evaluaciones_solicitadas": result.evals_requested,
        "evaluaciones_efectivas": result.evals_effective,
        "reutilizacion_cache": result.evals_requested - result.evals_effective,
        "poblacion_final": {
            "combinaciones_distintas": last["combinaciones_distintas"],
            "aptitud_media": last["aptitud_media"],
            "aptitud_max": last["aptitud_max"],
        },
        "total_hijos_reparados": sum(r["hijos_reparados"] for r in result.log),
        "total_individuos_invalidos_registrados": sum(r["individuos_invalidos"] for r in result.log),
    }


def run_and_save(exp: ExperimentConfig, seed: int, catalog: Catalog, base_weights: Weights, out_dir: Path,
                 is_main: bool = False, replica: int | None = None, verbose: bool = False) -> dict:
    """Ejecuta una corrida y guarda su log por generacion y su resumen."""
    result = run_ga(catalog, exp.weights, exp.ga, seed, exp.config_id, verbose=verbose)
    summary = build_summary(exp, result, catalog, base_weights, is_main)
    summary["replica"] = replica
    log_path, summary_path = run_paths(out_dir, exp.config_id, seed)
    write_rows_csv(log_path, result.log, LOG_FIELDS)
    write_json(summary_path, summary)
    summary["_log_path"] = str(log_path)
    return summary
