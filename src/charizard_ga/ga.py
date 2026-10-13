"""Algoritmo genetico con DEAP: ciclo evolutivo explicito y registro por generacion.

Flujo de una corrida (ver run_ga):
    0. Semilla: random.seed(semilla) y numpy.random.seed(semilla).
    1. Poblacion inicial: N movesets de 4 movimientos muestreados sin reemplazo.
    2. Evaluacion de la generacion 0.
    3. Para cada generacion g = 1..G:
         a) Elitismo: se copian (clonan) los E mejores individuos; no pasan por cruza ni mutacion.
         b) Seleccion: se eligen N - E padres (torneo, ruleta, ranking o control sobre numero esperado).
         c) Clonacion de los padres seleccionados (DEAP selecciona referencias, no copias).
         d) Cruza por pareja con probabilidad cx_prob (de conjuntos; o simple/binomial + reparacion).
         e) Mutacion por individuo (reemplaza un gen) con probabilidad fija o adaptativa por convergencia.
         f) Evaluacion solo de los individuos modificados (fitness invalidado).
         g) Reemplazo generacional: nueva poblacion = elites + hijos (tamano constante N).
         h) Actualizacion de la mejor solucion de TODA la corrida (copia independiente).
    4. Paro: al completar G generaciones o, con paro por estancamiento, cuando la mejor solucion no
       mejora durante `patience` generaciones seguidas (G queda como tope).
"""
from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass, field
from functools import partial

import numpy as np
from deap import base, creator, tools

from .config import GAConfig
from .data import Catalog
from .fitness import (DEFAULT_FITNESS, Evaluator, Weights, canonical_key, components, contributions,
                      validate_moveset, weighted_fitness)
from .operators import (OperatorCounters, adaptive_mutation_prob, cx_one_point_repair, cx_set, cx_uniform_repair,
                        mut_replace_one, random_moveset, sel_expected_count, sel_ranking, sel_roulette_safe)

FITNESS_CLASS = "FitnessMaxCharizard"
INDIVIDUAL_CLASS = "MovesetIndividual"


def ensure_deap_types():
    """Crea las clases de DEAP una sola vez.

    creator.create agrega clases globales al modulo deap.creator; volver a crearlas (por ejemplo al
    reejecutar una celda del notebook) produce advertencias. Como estas clases no dependen de
    ningun parametro de la corrida, se crean solo si no existen y se reutilizan.
    """
    if not hasattr(creator, FITNESS_CLASS):
        creator.create(FITNESS_CLASS, base.Fitness, weights=(1.0,))  # un objetivo, a MAXIMIZAR
    if not hasattr(creator, INDIVIDUAL_CLASS):
        creator.create(INDIVIDUAL_CLASS, list, fitness=getattr(creator, FITNESS_CLASS))


def build_toolbox(catalog: Catalog, cfg: GAConfig, evaluator: Evaluator, counters: OperatorCounters) -> base.Toolbox:
    """Registra en un Toolbox NUEVO (uno por corrida) los operadores elegidos en la configuracion."""
    ensure_deap_types()
    Individual = getattr(creator, INDIVIDUAL_CLASS)
    tb = base.Toolbox()
    # Inicializacion: cada individuo es una lista de 4 IDs distintos.
    tb.register("individual", tools.initIterate, Individual, partial(random_moveset, catalog.ids))
    tb.register("population", tools.initRepeat, list, tb.individual)
    tb.register("evaluate", evaluator)
    # Seleccion. Nota: los ejemplos docentes registran tools.selBest como "Ranking", pero selBest
    # elige deterministicamente a los mejores; aqui selBest solo se usa para el elitismo y el ranking
    # es probabilistico (operators.sel_ranking).
    if cfg.selection == "tournament":
        tb.register("select", tools.selTournament, tournsize=cfg.tournament_size)
    elif cfg.selection == "roulette":
        tb.register("select", sel_roulette_safe)
    elif cfg.selection == "ranking":
        tb.register("select", sel_ranking)
    else:
        tb.register("select", sel_expected_count)
    # Cruza: de conjuntos (no genera repetidos) o por posicion con reparacion de duplicados.
    if cfg.crossover == "set":
        tb.register("mate", cx_set, counters=counters)
    elif cfg.crossover == "uniform":
        tb.register("mate", cx_uniform_repair, indpb=cfg.cx_indpb, ids=catalog.ids, counters=counters)
    else:
        tb.register("mate", cx_one_point_repair, ids=catalog.ids, counters=counters)
    # Mutacion por reemplazo de un gen.
    tb.register("mutate", mut_replace_one, ids=catalog.ids, counters=counters)
    return tb


@dataclass
class RunResult:
    """Todo lo que produce una corrida (se guarda como log CSV + resumen JSON)."""

    config_id: str
    seed: int
    ga: dict
    weights: dict
    dataset_version: str
    fitness_version: str
    log: list = field(default_factory=list)
    best_moveset: tuple = ()
    best_fitness: float = 0.0
    best_generation: int = 0
    generations_executed: int = 0
    stop_reason: str = ""
    elapsed_seconds: float = 0.0
    evals_requested: int = 0
    evals_effective: int = 0
    candidates_generated: int = 0
    final_population: list = field(default_factory=list)


def _record(gen, pop, catalog, best_ever, best_gen, evaluator, prev, counters, mut_prob=None) -> dict:
    """Fila del log de la generacion `gen` (estadisticas de la poblacion ya reemplazada)."""
    fits = [ind.fitness.values[0] for ind in pop]
    gen_best = tools.selBest(pop, 1)[0]
    return {
        "generacion": gen,
        "tam_poblacion": len(pop),
        "prob_mutacion": mut_prob,   # probabilidad usada en esta generacion (vacia en la generacion 0)
        "aptitud_min": min(fits),
        "aptitud_media": statistics.fmean(fits),
        "aptitud_max": max(fits),
        "aptitud_desvio": statistics.pstdev(fits),
        "mejor_acumulada": best_ever.fitness.values[0],
        "generacion_mejor_acumulada": best_gen,
        "combinaciones_distintas": len({canonical_key(ind) for ind in pop}),
        "individuos_invalidos": sum(1 for ind in pop if not validate_moveset(ind, catalog)[0]),
        "evaluaciones_solicitadas": evaluator.requested - prev[0],
        "evaluaciones_efectivas": evaluator.effective - prev[1],
        "evaluaciones_solicitadas_acum": evaluator.requested,
        "evaluaciones_efectivas_acum": evaluator.effective,
        "cruzas": counters.crossovers,
        "mutaciones": counters.mutations,
        "hijos_reparados": counters.repaired_children,
        "genes_reparados": counters.repaired_genes,
        "mejor_generacion_moveset": "|".join(catalog.moves[m].slug for m in canonical_key(gen_best)),
        "mejor_acumulada_moveset": "|".join(catalog.moves[m].slug for m in canonical_key(best_ever)),
    }


def run_ga(catalog: Catalog, weights: Weights, cfg: GAConfig, seed: int, config_id: str = "",
           verbose: bool = False, print_every: int = 20) -> RunResult:
    """Ejecuta UNA corrida del AG y devuelve su log y su mejor solucion."""
    # 0) Semillas: todas las decisiones aleatorias (DEAP y operadores propios) usan `random`.
    random.seed(seed)
    np.random.seed(seed)  # numpy no participa del AG; se fija igual por prolijidad.

    # cache propia: no se mezclan pesos, datasets ni versiones de la aptitud
    evaluator = Evaluator(catalog, weights, cfg.fitness_version)
    counters = OperatorCounters()
    tb = build_toolbox(catalog, cfg, evaluator, counters)
    N, E = cfg.population_size, cfg.elitism
    t0 = time.perf_counter()

    # 1-2) Poblacion inicial y su evaluacion.
    pop = tb.population(n=N)
    for ind in pop:
        ind.fitness.values = tb.evaluate(ind)
    best_ever = tb.clone(tools.selBest(pop, 1)[0])   # copia: no cambia aunque la poblacion cambie
    best_gen = 0
    result = RunResult(config_id=config_id, seed=seed, ga=cfg.to_dict(), weights=weights.to_dict(),
                       dataset_version=catalog.dataset_version, fitness_version=cfg.fitness_version)
    prev = (0, 0)
    result.log.append(_record(0, pop, catalog, best_ever, best_gen, evaluator, prev, counters))
    candidates = N
    executed = 0
    stagnated = False
    if verbose:
        _print_progress(result.log[-1], catalog)

    # 3) Ciclo evolutivo.
    for gen in range(1, cfg.generations + 1):
        counters.reset()
        prev = (evaluator.requested, evaluator.effective)
        # Probabilidad de mutacion de esta generacion: fija, o adaptativa segun la aptitud media de la
        # poblacion actual (sube cuando la poblacion converge).
        if cfg.mutation_mode == "adaptive":
            mut_prob = adaptive_mutation_prob([ind.fitness.values[0] for ind in pop], cfg.mutation_prob,
                                              cfg.mutation_prob_max, cfg.convergence_threshold)
        else:
            mut_prob = cfg.mutation_prob

        # a) Elitismo: copias de los E mejores (protegidas de la variacion).
        elites = [tb.clone(ind) for ind in tools.selBest(pop, E)] if E > 0 else []

        # b-c) Seleccion de N-E padres y clonacion.
        offspring = [tb.clone(ind) for ind in tb.select(pop, N - E)]

        # d) Cruza por pareja: (0,1), (2,3), ... Si N-E es impar, el ultimo pasa sin cruzarse.
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < cfg.cx_prob:
                tb.mate(child1, child2)
                del child1.fitness.values   # la aptitud previa ya no corresponde al nuevo cromosoma
                del child2.fitness.values

        # e) Mutacion por individuo.
        for child in offspring:
            if random.random() < mut_prob:
                tb.mutate(child)
                del child.fitness.values

        # f) Evaluacion de los individuos con aptitud invalidada (la cache evita recalcular repetidos).
        for child in offspring:
            if not child.fitness.valid:
                child.fitness.values = tb.evaluate(child)
        candidates += len(offspring)

        # g) Reemplazo generacional con tamano constante.
        pop[:] = elites + offspring
        if len(pop) != N:
            raise RuntimeError("El tamano de la poblacion cambio")

        # h) Mejor de toda la corrida (solo se reemplaza ante una mejora estricta).
        gen_best = tools.selBest(pop, 1)[0]
        if gen_best.fitness.values[0] > best_ever.fitness.values[0] + 1e-12:
            best_ever = tb.clone(gen_best)
            best_gen = gen

        result.log.append(_record(gen, pop, catalog, best_ever, best_gen, evaluator, prev, counters, mut_prob))
        executed = gen
        if verbose and (gen % print_every == 0 or gen == cfg.generations):
            _print_progress(result.log[-1], catalog)

        # 4a) Paro por estancamiento: la mejor solucion no mejoro durante `patience` generaciones seguidas.
        if cfg.stop_criterion == "stagnation" and gen - best_gen >= cfg.patience:
            stagnated = True
            break

    # 4b) Paro por cantidad de generaciones (o tope del paro por estancamiento).
    result.elapsed_seconds = time.perf_counter() - t0
    result.generations_executed = executed
    if stagnated:
        result.stop_reason = (f"estancamiento: la mejor solucion no mejoro durante {cfg.patience} generaciones "
                              f"(ultima mejora en la generacion {best_gen})")
    else:
        result.stop_reason = f"se completaron las {cfg.generations} generaciones configuradas (criterio de paro por generaciones)"
    result.best_moveset = canonical_key(best_ever)
    result.best_fitness = best_ever.fitness.values[0]
    result.best_generation = best_gen
    result.evals_requested = evaluator.requested
    result.evals_effective = evaluator.effective
    result.candidates_generated = candidates
    result.final_population = [canonical_key(ind) for ind in pop]
    return result


def describe_solution(moveset, catalog: Catalog, weights: Weights, base_weights: Weights | None = None,
                      version: str = DEFAULT_FITNESS) -> dict:
    """Decodifica un moveset: movimientos, componentes, aportes, aptitud propia y bajo el perfil base."""
    ok, reason = validate_moveset(moveset, catalog)
    if not ok:
        return {"valido": False, "motivo": reason, "aptitud": 0.0}
    comp = components(moveset, catalog, version)
    out = {
        "valido": True,
        "version_aptitud": version,
        "movimientos": [
            {"move_id": m, "slug": catalog.moves[m].slug, "nombre_es": catalog.moves[m].nombre_es,
             "tipo": catalog.moves[m].tipo, "tipo_es": catalog.moves[m].tipo_es, "potencia": catalog.moves[m].potencia,
             "potencia_efectiva": catalog.moves[m].potencia_efectiva,
             "precision": catalog.moves[m].precision, "categoria": catalog.moves[m].categoria, "stab": catalog.moves[m].stab,
             "efectos_ignorados": catalog.moves[m].efectos_ignorados}
            for m in canonical_key(moveset)
        ],
        "componentes": dict(zip(("C", "P", "A", "S", "D"), comp.as_tuple())),
        "aportes": contributions(comp, weights),
        "aptitud": weighted_fitness(comp, weights),
        "tipos_cubiertos": list(comp.covered),
        "tipos_no_cubiertos": list(comp.uncovered),
        "n_tipos_cubiertos": len(comp.covered),
    }
    if base_weights is not None:
        out["aptitud_perfil_base"] = weighted_fitness(comp, base_weights)
    return out


def _print_progress(row: dict, catalog: Catalog):
    print(f"gen {row['generacion']:3d} | max {row['aptitud_max']:.4f} | media {row['aptitud_media']:.4f} | "
          f"mejor acumulada {row['mejor_acumulada']:.4f} | distintas {row['combinaciones_distintas']:3d} | "
          f"mejor: {row['mejor_acumulada_moveset']}")
