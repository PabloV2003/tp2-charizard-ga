"""Operadores geneticos adaptados a un cromosoma de 4 movimientos distintos.

Toda la aleatoriedad usa el modulo `random` de Python, que es tambien el que usa DEAP
internamente (selTournament, selRoulette, cxUniform, cxOnePoint). Cada corrida fija la semilla
con random.seed(semilla) antes de empezar, de modo que UNA sola fuente de aleatoriedad
controla inicializacion, seleccion, cruza, reparacion y mutacion.

Metodos de la teoria de la catedra (Algoritmos Geneticos, Pollo Cattaneo y Castro):
    seleccion: torneo (diap. 24), ranking (25), ruleta (27-28), control sobre numero esperado (29-32);
    cruza: simple (34), binomial aleatoria (37) y una cruza propia del problema (nota de la diap. 33);
    mutacion: simple y adaptativa por convergencia (39).
"""
from __future__ import annotations

import random
import statistics

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


def sel_ranking(individuals, k):
    """Ranking lineal: la probabilidad depende de la POSICION en el orden por aptitud, no de su valor.

    El mejor de N individuos pesa N, el segundo N-1, ..., el peor 1. A diferencia de la ruleta, no
    importa si las aptitudes estan muy juntas o muy separadas. (Los ejemplos de la catedra registran
    tools.selBest como "Ranking", pero selBest elige siempre a los mejores: no es esta seleccion.)
    """
    ranked = sorted(individuals, key=lambda ind: ind.fitness.values[0], reverse=True)
    n = len(ranked)
    return random.choices(ranked, weights=[n - i for i in range(n)], k=k)


def sel_expected_count(individuals, k):
    """Control sobre numero esperado: cada individuo se copia tantas veces como indica su aptitud.

    Numero esperado = aptitud / suma de aptitudes * k. La parte entera entra directo a la seleccion
    (asegura a los mejores); los lugares que faltan se completan con una ruleta sobre las partes
    decimales (las "mantisas"). Al final se mezcla el orden para que las parejas de cruza no sean
    copias del mismo individuo.
    """
    fits = [ind.fitness.values[0] for ind in individuals]
    total = sum(fits)
    if total <= 0:
        return tools.selRandom(individuals, k)
    expected = [f / total * k for f in fits]
    chosen = []
    for ind, e in zip(individuals, expected):
        chosen.extend([ind] * int(e))
    rest = k - len(chosen)
    if rest > 0:
        mantisas = [e - int(e) for e in expected]
        if sum(mantisas) > 0:
            chosen.extend(random.choices(individuals, weights=mantisas, k=rest))
        else:
            chosen.extend(tools.selRandom(individuals, rest))
    random.shuffle(chosen)
    return chosen


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
def cx_set(ind1, ind2, counters: OperatorCounters):
    """Cruza de conjuntos: binomial aleatoria que conserva los genes comunes (cruza por defecto).

    El moveset es un conjunto (el orden no importa), pero las cruzas por posicion pueden perder un
    movimiento que tenian AMBOS padres si esta en posiciones distintas: con la binomial aleatoria pasa
    en aproximadamente 1 de cada 3 hijos (la teoria advierte que "rompe bloques" y que hay que evaluarla
    segun la representacion). Aca:
      - los movimientos que comparten ambos padres pasan a los dos hijos;
      - las posiciones restantes se completan al azar, sin repetir, con los demas genes de los padres.
    Ejemplo: [a,b,c,d] x [e,a,f,g] -> ambos hijos tienen 'a' y tres de {b,c,d,e,f,g}.
    Nunca genera repetidos, por lo que no necesita reparacion.
    """
    common = [g for g in ind1 if g in ind2]
    rest = list(dict.fromkeys(g for g in list(ind1) + list(ind2) if g not in common))
    for child in (ind1, ind2):
        child[:] = common + random.sample(rest, MOVESET_SIZE - len(common))
    counters.crossovers += 1
    return ind1, ind2


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


def adaptive_mutation_prob(fits: list, base: float, maximum: float, threshold: float) -> float:
    """Mutacion adaptativa por convergencia: la probabilidad depende de la aptitud media de la poblacion.

    Mientras la poblacion es diversa (media / maxima < threshold) se usa `base`. Cuando la media se
    acerca a la maxima (la poblacion convergio), la probabilidad sube linealmente hasta `maximum`,
    para volver a explorar y evitar la convergencia prematura.
    """
    best = max(fits)
    if best <= 0:
        return base
    ratio = statistics.fmean(fits) / best
    t = min(1.0, max(0.0, (ratio - threshold) / (1.0 - threshold)))
    return base + (maximum - base) * t
