"""Metodos de comparacion que usan EXACTAMENTE el mismo catalogo y la misma funcion de aptitud.

    - exhaustive_*: enumeracion completa de las C(M,4) combinaciones (optimo exacto del modelo).
    - random_search: muestreo aleatorio de movesets validos con semilla y presupuesto registrados.
    - greedy: construccion voraz por ganancia marginal de aptitud (reglas deterministas).
    - local_search: ascenso de colina por intercambio de un movimiento (mejor mejora).
"""
from __future__ import annotations

import itertools
import math
import random
import time
from dataclasses import dataclass

import numpy as np

from .data import Catalog
from .fitness import (COMPONENT_NAMES, Evaluator, Weights, canonical_key, components, partial_components,
                      weighted_fitness)

TOL = 1e-9


# ---------------------------------------------------------------------------
# Enumeracion exhaustiva
# ---------------------------------------------------------------------------
@dataclass
class ExhaustiveTable:
    """Componentes de TODAS las combinaciones (no dependen de los pesos)."""

    keys: np.ndarray          # (n, 4) IDs ordenados
    comps: np.ndarray         # (n, 5) columnas C, P, A, S, D
    seconds: float            # tiempo de enumeracion + calculo de componentes
    allowed_ids: tuple
    catalog: Catalog

    @property
    def n(self) -> int:
        return len(self.keys)

    def fitness(self, weights: Weights) -> np.ndarray:
        # Misma ponderacion que fitness.weighted_fitness, aplicada a todas las filas.
        return 100.0 * self.comps @ np.array(weights.as_tuple())


def exhaustive_table(catalog: Catalog, allowed_ids=None) -> ExhaustiveTable:
    """Enumera todas las combinaciones de 4 movimientos y calcula sus componentes con fitness.components."""
    ids = tuple(sorted(allowed_ids)) if allowed_ids is not None else catalog.ids
    t0 = time.perf_counter()
    n = math.comb(len(ids), 4)
    keys = np.empty((n, 4), dtype=np.int32)
    comps = np.empty((n, 5), dtype=np.float64)
    for i, combo in enumerate(itertools.combinations(ids, 4)):
        keys[i] = combo
        comps[i] = components(combo, catalog).as_tuple()
    return ExhaustiveTable(keys=keys, comps=comps, seconds=time.perf_counter() - t0, allowed_ids=ids, catalog=catalog)


def exhaustive_optimum(table: ExhaustiveTable, weights: Weights, top_k: int = 10) -> dict:
    """Optimo exacto de un perfil, cantidad de empates y ranking de las mejores combinaciones."""
    t0 = time.perf_counter()
    fit = table.fitness(weights)
    best = float(fit.max())
    ties = np.flatnonzero(fit >= best - TOL)
    order = np.argsort(-fit, kind="stable")[:top_k]
    # El valor del optimo se recalcula con la MISMA ruta de codigo que usa el AG
    # (fitness.weighted_fitness), para que la brecha no dependa del orden de suma de numpy.
    best_key = tuple(int(x) for x in table.keys[ties[0]])
    best = weighted_fitness(components(best_key, table.catalog), weights)
    return {
        "optimo": best,
        "n_empates_optimo": int(len(ties)),
        "movesets_optimos": [tuple(int(x) for x in table.keys[i]) for i in ties],
        "top": [(tuple(int(x) for x in table.keys[i]), float(fit[i])) for i in order],
        "segundos_puntuacion": time.perf_counter() - t0,
        "fitness_array": fit,
    }


def rank_of(table: ExhaustiveTable, fit: np.ndarray, value: float) -> int:
    """Posicion (1 = mejor) de un valor de aptitud entre todas las combinaciones (empates comparten puesto)."""
    return int(np.sum(fit > value + TOL)) + 1


# ---------------------------------------------------------------------------
# Busqueda aleatoria
# ---------------------------------------------------------------------------
def random_search(catalog: Catalog, weights: Weights, budget: int, seed: int, budget_mode: str = "requested",
                  record_curve: bool = False) -> dict:
    """Genera movesets validos al azar (4 movimientos sin reemplazo) y conserva el mejor.

    budget_mode = "requested": se generan exactamente `budget` candidatos (evaluaciones solicitadas).
    budget_mode = "effective": se generan candidatos hasta evaluar `budget` combinaciones DISTINTAS.
    Usa un generador propio random.Random(seed) para no interferir con otras fuentes de azar.
    """
    if budget_mode not in ("requested", "effective"):
        raise ValueError(budget_mode)
    rng = random.Random(seed)
    ev = Evaluator(catalog, weights)
    best_key, best_val = None, -1.0
    curve = []  # (evaluaciones efectivas acumuladas, evaluaciones solicitadas, mejor hasta el momento)
    t0 = time.perf_counter()
    while (ev.requested if budget_mode == "requested" else ev.effective) < budget:
        cand = rng.sample(catalog.ids, 4)
        val = ev.value(cand)
        if val > best_val + 1e-12:
            best_val, best_key = val, canonical_key(cand)
        if record_curve:
            curve.append((ev.effective, ev.requested, best_val))
    return {
        "metodo": "busqueda_aleatoria",
        "modo_presupuesto": budget_mode,
        "semilla": seed,
        "presupuesto": budget,
        "mejor_moveset": best_key,
        "mejor_aptitud": best_val,
        "evaluaciones_solicitadas": ev.requested,
        "evaluaciones_efectivas": ev.effective,
        "segundos": time.perf_counter() - t0,
        "curva": curve,
    }


# ---------------------------------------------------------------------------
# Heuristica voraz y busqueda local
# ---------------------------------------------------------------------------
def greedy(catalog: Catalog, weights: Weights) -> dict:
    """Construccion voraz: en cada paso agrega el movimiento con mayor aptitud parcial.

    Reglas: (1) se parte del moveset vacio; (2) en cada uno de los 4 pasos se evalua cada movimiento
    no elegido con partial_components (casillas vacias aportan 0, mismas normalizaciones que F);
    (3) se agrega el de mayor valor; los empates se resuelven por el menor ID de movimiento.
    Con 4 movimientos el valor parcial coincide con F, por lo que el resultado final es F exacta.
    """
    w = np.array(weights.as_tuple())
    chosen: list = []
    evaluations = 0
    t0 = time.perf_counter()
    steps = []
    for _ in range(4):
        best_m, best_v = None, -1.0
        for m in catalog.ids:  # IDs en orden creciente -> desempate determinista
            if m in chosen:
                continue
            evaluations += 1
            v = 100.0 * float(np.dot(w, partial_components(chosen + [m], catalog)))
            if v > best_v + 1e-12:
                best_m, best_v = m, v
        chosen.append(best_m)
        steps.append((catalog.moves[best_m].slug, best_v))
    key = canonical_key(chosen)
    ev = Evaluator(catalog, weights)
    return {
        "metodo": "voraz",
        "mejor_moveset": key,
        "mejor_aptitud": ev.value(key),
        "evaluaciones_solicitadas": evaluations,
        "evaluaciones_efectivas": evaluations,
        "pasos": steps,
        "segundos": time.perf_counter() - t0,
    }


def local_search(catalog: Catalog, weights: Weights, start) -> dict:
    """Ascenso de colina: prueba todos los intercambios de 1 movimiento y aplica la mejor mejora.

    Se detiene cuando ningun intercambio mejora la aptitud (optimo local respecto de ese vecindario).
    """
    ev = Evaluator(catalog, weights)
    current = list(canonical_key(start))
    current_val = ev.value(current)
    iterations = 0
    t0 = time.perf_counter()
    while True:
        best_neighbor, best_val = None, current_val
        for pos in range(4):
            for m in catalog.ids:
                if m in current:
                    continue
                neighbor = current.copy()
                neighbor[pos] = m
                val = ev.value(neighbor)
                if val > best_val + 1e-12:
                    best_neighbor, best_val = neighbor, val
        if best_neighbor is None:
            break
        current, current_val = list(canonical_key(best_neighbor)), best_val
        iterations += 1
    return {
        "metodo": "voraz+busqueda_local",
        "mejor_moveset": canonical_key(current),
        "mejor_aptitud": current_val,
        "iteraciones": iterations,
        "evaluaciones_solicitadas": ev.requested,
        "evaluaciones_efectivas": ev.effective,
        "segundos": time.perf_counter() - t0,
    }


def component_dict(row) -> dict:
    return dict(zip(COMPONENT_NAMES, (float(x) for x in row)))
