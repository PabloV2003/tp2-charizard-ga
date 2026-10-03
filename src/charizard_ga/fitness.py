"""Funcion de aptitud aprobada en la entrega parcial.

    F(x) = 100 * (wC*C(x) + wP*P(x) + wA*A(x) + wS*S(x) + wD*D(x))

Componentes (todos en [0, 1]):
    C(x): tipos defensores individuales (de 18) con al menos un movimiento de multiplicador > 1, / 18.
    P(x): potencia base promedio de los 4 movimientos / potencia maxima del catalogo completo.
    A(x): precision promedio de los 4 movimientos / 100.
    S(x): cantidad de movimientos de tipo Fuego o Volador / 4  (presencia de STAB; NO multiplica P).
    D(x): cantidad de tipos distintos entre los 4 movimientos / 4.

Un individuo invalido (longitud distinta de 4, movimientos repetidos o fuera del catalogo) recibe 0.
El calculo de componentes esta separado de la ponderacion: los componentes no dependen de los pesos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .data import TYPE_ORDER, Catalog

# Identificador de la version de la formula. Se guarda en cada log para que los resultados
# puedan rastrearse a la definicion exacta de aptitud con la que fueron calculados.
FITNESS_VERSION = "F1 (C/P/A/S/D; P normalizada por la potencia máxima del catálogo)"
MOVESET_SIZE = 4
N_TYPES = len(TYPE_ORDER)
COMPONENT_NAMES = ("C", "P", "A", "S", "D")


@dataclass(frozen=True)
class Weights:
    """Vector de pesos (wC, wP, wA, wS, wD): no negativos y con suma 1."""

    wC: float
    wP: float
    wA: float
    wS: float
    wD: float

    def __post_init__(self):
        values = self.as_tuple()
        if any(w < 0 for w in values):
            raise ValueError(f"Los pesos deben ser no negativos: {values}")
        if not math.isclose(sum(values), 1.0, abs_tol=1e-9):
            raise ValueError(f"Los pesos deben sumar 1 (suman {sum(values)})")

    def as_tuple(self) -> tuple:
        return (self.wC, self.wP, self.wA, self.wS, self.wD)

    @classmethod
    def from_dict(cls, d: dict) -> "Weights":
        return cls(d["wC"], d["wP"], d["wA"], d["wS"], d["wD"])

    def to_dict(self) -> dict:
        return dict(zip(("wC", "wP", "wA", "wS", "wD"), self.as_tuple()))


@dataclass(frozen=True)
class Components:
    """Componentes normalizados de un moveset y la informacion de cobertura asociada."""

    C: float
    P: float
    A: float
    S: float
    D: float
    covered: tuple      # tipos defensores cubiertos con superefectividad (orden canonico)
    uncovered: tuple    # tipos defensores sin cobertura superefectiva

    def as_tuple(self) -> tuple:
        return (self.C, self.P, self.A, self.S, self.D)


def validate_moveset(moveset, catalog: Catalog) -> tuple[bool, str]:
    """Restricciones duras: exactamente 4 IDs, sin repetir y todos pertenecientes al catalogo."""
    try:
        genes = list(moveset)
    except TypeError:
        return False, "el individuo no es una secuencia"
    if len(genes) != MOVESET_SIZE:
        return False, f"longitud {len(genes)} distinta de {MOVESET_SIZE}"
    try:
        distinct = set(genes)
    except TypeError:
        return False, "genes no hashables"
    if len(distinct) != MOVESET_SIZE:
        return False, "movimientos repetidos"
    missing = [g for g in genes if g not in catalog.moves]
    if missing:
        return False, f"movimientos fuera del catalogo permitido: {missing}"
    return True, ""


def components(moveset, catalog: Catalog) -> Components:
    """Calcula C, P, A, S y D de un moveset VALIDO (no aplica pesos)."""
    moves = [catalog.moves[g] for g in moveset]
    covered = set()
    for mv in moves:
        covered |= catalog.se_types[mv.tipo]          # cada tipo cubierto cuenta una sola vez
    n = len(moves)
    return Components(
        C=len(covered) / N_TYPES,
        P=(sum(mv.potencia for mv in moves) / n) / catalog.power_max,
        A=(sum(mv.precision for mv in moves) / n) / 100.0,
        S=sum(1 for mv in moves if mv.stab) / MOVESET_SIZE,
        D=len({mv.tipo for mv in moves}) / MOVESET_SIZE,
        covered=tuple(t for t in TYPE_ORDER if t in covered),
        uncovered=tuple(t for t in TYPE_ORDER if t not in covered),
    )


def weighted_fitness(comp: Components, weights: Weights) -> float:
    """Ponderacion de los componentes: F = 100 * sum(w_k * componente_k)."""
    return 100.0 * sum(w * c for w, c in zip(weights.as_tuple(), comp.as_tuple()))


def contributions(comp: Components, weights: Weights) -> dict:
    """Aporte de cada componente a la aptitud (en puntos de F)."""
    return {name: 100.0 * w * c for name, w, c in zip(COMPONENT_NAMES, weights.as_tuple(), comp.as_tuple())}


def fitness(moveset, catalog: Catalog, weights: Weights) -> float:
    """Aptitud completa: 0 si el individuo es invalido; si no, la ponderacion de sus componentes."""
    ok, _ = validate_moveset(moveset, catalog)
    if not ok:
        return 0.0
    return weighted_fitness(components(moveset, catalog), weights)


def partial_components(moves_subset, catalog: Catalog) -> tuple:
    """Componentes de un moveset INCOMPLETO (k <= 4) con las casillas vacias aportando 0.

    Solo la usa la heuristica voraz para medir ganancia marginal. Con k = 4 coincide exactamente
    con components() (se verifica en las pruebas).
    """
    moves = [catalog.moves[g] for g in moves_subset]
    covered = set()
    for mv in moves:
        covered |= catalog.se_types[mv.tipo]
    return (
        len(covered) / N_TYPES,
        sum(mv.potencia for mv in moves) / (MOVESET_SIZE * catalog.power_max),
        sum(mv.precision for mv in moves) / (MOVESET_SIZE * 100.0),
        sum(1 for mv in moves if mv.stab) / MOVESET_SIZE,
        len({mv.tipo for mv in moves}) / MOVESET_SIZE,
    )


def canonical_key(moveset) -> tuple:
    """Clave independiente del orden: identifica combinaciones equivalentes (cache y diversidad)."""
    return tuple(sorted(moveset))


class Evaluator:
    """Evaluador con cache para el AG y las lineas base.

    La cache se indexa por la clave ordenada del moveset y pertenece a UN solo par
    (dataset, pesos): cada corrida crea su propio Evaluator, por lo que nunca se reutiliza
    una aptitud calculada con otros pesos u otro dataset.
    Contadores:
        requested -> evaluaciones solicitadas (incluye aciertos de cache).
        effective -> evaluaciones efectivas (calculos reales; fallos de cache).
        invalid   -> individuos invalidos evaluados (reciben 0).
    """

    def __init__(self, catalog: Catalog, weights: Weights):
        self.catalog = catalog
        self.weights = weights
        self.identity = (catalog.dataset_version, weights.as_tuple(), FITNESS_VERSION)
        self._cache: dict = {}
        self.requested = 0
        self.effective = 0
        self.invalid = 0

    def value(self, moveset) -> float:
        self.requested += 1
        ok, _ = validate_moveset(moveset, self.catalog)
        if not ok:
            self.invalid += 1
            return 0.0
        key = canonical_key(moveset)
        cached = self._cache.get(key)
        if cached is None:
            self.effective += 1
            cached = weighted_fitness(components(key, self.catalog), self.weights)
            self._cache[key] = cached
        return cached

    def __call__(self, individual) -> tuple:
        # DEAP espera una tupla con un valor por objetivo.
        return (self.value(individual),)

    @property
    def cache_size(self) -> int:
        return len(self._cache)
