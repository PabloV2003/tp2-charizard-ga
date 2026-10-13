"""Demostracion por consola: ejecuta UNA corrida del AG y muestra la mejor solucion.

Ejemplos:
    python scripts/run_ga.py                         # R1 (perfil base), semilla 42
    python scripts/run_ga.py --config R3 --seed 45   # otra configuracion y semilla
    python scripts/run_ga.py --config R1 --generations 50 --mutation-prob 0.2
    python scripts/run_ga.py --selection ranking --mutation-mode adaptive --stop stagnation
    python scripts/run_ga.py --fitness F1 --crossover uniform   # version original, para comparar

Los archivos de la demostracion se guardan en results/demo/ (no pisan los resultados del lote).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charizard_ga.config import CROSSOVERS, MUTATION_MODES, SELECTIONS, STOP_CRITERIA, load_experiments  # noqa: E402
from charizard_ga.fitness import FITNESS_VERSIONS  # noqa: E402
from charizard_ga.data import load_catalog  # noqa: E402
from charizard_ga.experiments import run_and_save  # noqa: E402
from charizard_ga.paths import RESULTS_DIR  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Corrida individual del AG de Charizard")
    parser.add_argument("--config", default="R1", help="identificador en config/experiments.json (R1..R5, ORIG-R1, OP-...)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--generations", type=int)
    parser.add_argument("--population", type=int)
    parser.add_argument("--selection", choices=list(SELECTIONS))
    parser.add_argument("--crossover", choices=list(CROSSOVERS))
    parser.add_argument("--mutation-prob", type=float)
    parser.add_argument("--mutation-mode", choices=list(MUTATION_MODES))
    parser.add_argument("--stop", choices=list(STOP_CRITERIA), help="criterio de paro")
    parser.add_argument("--patience", type=int, help="generaciones sin mejora (paro por estancamiento)")
    parser.add_argument("--fitness", choices=list(FITNESS_VERSIONS), help="version de la funcion de aptitud")
    parser.add_argument("--out", default=str(RESULTS_DIR / "demo"))
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    catalog = load_catalog()
    exps = load_experiments()
    exp = next((c for c in exps["configs"] if c.config_id == args.config), None)
    if exp is None:
        raise SystemExit(f"Configuracion desconocida: {args.config}")
    overrides = {k: v for k, v in {
        "generations": args.generations, "population_size": args.population, "selection": args.selection,
        "crossover": args.crossover, "mutation_prob": args.mutation_prob, "mutation_mode": args.mutation_mode,
        "stop_criterion": args.stop, "patience": args.patience, "fitness_version": args.fitness}.items() if v is not None}
    if overrides:
        exp = replace(exp, ga=exp.ga.with_overrides(overrides), overrides={**exp.overrides, **overrides},
                      config_id=exp.config_id + "-demo")

    print(f"Catalogo: M = {catalog.M} movimientos (dataset {catalog.dataset_version}); configuracion {exp.config_id}; semilla {args.seed}")
    print(f"Pesos: {exp.weights.to_dict()}")
    print(f"Parametros AG: {exp.ga.to_dict()}\n")
    summary = run_and_save(exp, args.seed, catalog, exps["profiles"][exps["base_profile"]], Path(args.out), verbose=True)
    best = summary["mejor_solucion"]
    print("\nMejor solucion de toda la corrida (generacion %d):" % best["generacion_encontrada"])
    for mv in best["movimientos"]:
        stab = "STAB" if mv["stab"] else "    "
        print(f"  - {mv['nombre_es']:<18} {mv['tipo_es']:<10} pot {mv['potencia']:>3} (efectiva {mv['potencia_efectiva']:5.1f})"
              f"  prec {mv['precision']:>3}  {stab}")
    comp = best["componentes"]
    print("Componentes: " + "  ".join(f"{k}={v:.4f}" for k, v in comp.items()))
    print(f"Aptitud {summary['fitness_version']} = {best['aptitud']:.4f}   (bajo el perfil base: {best['aptitud_perfil_base']:.4f})")
    print(f"Paro: {summary['motivo_paro']}")
    print(f"Tipos cubiertos ({best['n_tipos_cubiertos']}/18): {', '.join(best['tipos_cubiertos'])}")
    print(f"Sin cobertura superefectiva: {', '.join(best['tipos_no_cubiertos'])}")
    print(f"Evaluaciones solicitadas {summary['evaluaciones_solicitadas']}, efectivas {summary['evaluaciones_efectivas']}; "
          f"tiempo {summary['tiempo_segundos']:.2f} s")
    print(f"Log: {summary['_log_path']}")


if __name__ == "__main__":
    main()
