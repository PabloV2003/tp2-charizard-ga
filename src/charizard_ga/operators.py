"""Operadores geneticos adaptados a un cromosoma de 4 movimientos distintos.

Toda la aleatoriedad usa el modulo `random` de Python, que es tambien el que usa DEAP
internamente (selTournament, selRoulette, cxUniform, cxOnePoint). Cada corrida fija la semilla
con random.seed(semilla) antes de empezar, de modo que UNA sola fuente de aleatoriedad
controla inicializacion, seleccion, cruza, reparacion y mutacion.
"""
from __future__ import annotations

import random

from deap import tools

from .fitness import MOVESET_SIZE


class OperatorCounters:
    """Contadores de lo que hicieron los operadores en la generacion actual (para el log)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.crossovers = 0          # parejas efectivamente cruzadas
        self.mutations = 0           # individuos mutados
        self.repaired_children = 0   # hijos que necesitaron reparacion tras la cruza
        self.repaired_genes = 0      # posiciones reparadas (genes duplicados reemplazados)


# ---------------------------------------------------------------------------
# Inicializacion
# ---------------------------------------------------------------------------
def random_moveset(ids: tuple) -> list:
    """Cuatro movimientos elegidos al azar SIN reemplazo: siempre es un individuo valido."""
    return random.sample(ids, MOVESET_SIZE)


# ---------------------------------------------------------------------------
# Seleccion
# ---------------------------------------------------------------------------
def sel_roulette_safe(individuals, k):
    """Ruleta (probabilidad proporcional a la aptitud) usando tools.selRoulette de DEAP.

    selRoulette no esta definida si la suma de aptitudes es 0 (todas las porciones serian
    nulas). En ese caso se elige al azar con probabilidad uniforme (tools.selRandom).
    """
    total = sum(ind.fitness.values[0] for ind in individuals)
    if total <= 0:
        return tools.selRandom(individuals, k)
    return tools.selRoulette(individuals, k)


# ---------------------------------------------------------------------------
# Reparacion de duplicados
# ---------------------------------------------------------------------------
def repair_duplicates(child, parent_pool: list, ids: tuple) -> int:
    """Repara un hijo con movimientos repetidos y devuelve cuantas posiciones se reemplazaron.

    - Se conservan los genes no repetidos (la primera aparicion de cada movimiento).
    - Cada posicion repetida se completa con un movimiento AUSENTE en el hijo, elegido al azar
      entre los genes de los padres (asi el hijo hereda material genetico de la pareja).
    - Si los padres no aportan genes disponibles, se elige al azar del resto del catalogo.
    Como el orden del moveset no tiene significado, que posicion conserva el gen no altera la aptitud.
    """
    seen = set()
    repeated_positions = []
    for pos, gene in enumerate(child):
        if gene in seen:
            repeated_positions.append(pos)
        else:
            seen.add(gene)
    if not repeated_positions:
        return 0
    candidates = [g for g in parent_pool if g not in seen]
    for pos in repeated_positions:
        if candidates:
            gene = random.choice(candidates)
            candidates.remove(gene)
        else:  # caso de respaldo; con padres validos no deberia ocurrir
            gene = random.choice([m for m in ids if m not in seen])
        child[pos] = gene
        seen.add(gene)
    return len(repeated_positions)


def _parent_pool(parent1, parent2) -> list:
    # Union ordenada y sin repetidos de los genes de ambos padres (orden determinista).
    return list(dict.fromkeys(list(parent1) + list(parent2)))


# ---------------------------------------------------------------------------
# Cruza (se aplica por PAREJA con probabilidad cx_prob, decidida en el ciclo del AG)
# ---------------------------------------------------------------------------
def cx_uniform_repair(ind1, ind2, indpb: float, ids: tuple, counters: OperatorCounters):
    """Cruza uniforme / binomial aleatoria: cada posicion se intercambia con probabilidad indpb.

    Usa tools.cxUniform de DEAP y luego repara los duplicados que pueda generar.
    Ejemplo: [a,b,c,d] x [e,a,f,g] intercambiando solo la posicion 0 produce
    [e,b,c,d] y [a,a,f,g]; el segundo hijo se repara reemplazando la 'a' repetida.
    """
    pool = _parent_pool(ind1, ind2)
    tools.cxUniform(ind1, ind2, indpb)
    _repair_pair(ind1, ind2, pool, ids, counters)
    return ind1, ind2


def cx_one_point_repair(ind1, ind2, ids: tuple, counters: OperatorCounters):
    """Cruza de un punto (tools.cxOnePoint): se intercambian las colas desde un corte aleatorio."""
    pool = _parent_pool(ind1, ind2)
    tools.cxOnePoint(ind1, ind2)
    _repair_pair(ind1, ind2, pool, ids, counters)
    return ind1, ind2


def _repair_pair(ind1, ind2, pool, ids, counters):
    counters.crossovers += 1
    for child in (ind1, ind2):
        fixed = repair_duplicates(child, pool, ids)
        if fixed:
            counters.repaired_children += 1
            counters.repaired_genes += fixed


# ---------------------------------------------------------------------------
# Mutacion (se aplica por INDIVIDUO con probabilidad mut_prob, decidida en el ciclo del AG)
# ---------------------------------------------------------------------------
def mut_replace_one(individual, ids: tuple, counters: OperatorCounters):
    """Reemplaza UN gen elegido al azar por un movimiento permitido ausente en el individuo.

    Se excluye tambien el gen actual, por lo que la mutacion siempre produce una combinacion nueva.
    No se usa mutShuffleIndexes (del ejemplo del viajero): intercambiar posiciones de un moveset
    no cambia la combinacion ni su aptitud.
    """
    pos = random.randrange(len(individual))
    present = set(individual)
    individual[pos] = random.choice([m for m in ids if m not in present])
    counters.mutations += 1
    return (individual,)
