"""Pruebas de inicializacion, cruza + reparacion, mutacion y seleccion."""
import random
from collections import Counter

import pytest
from deap import creator

from charizard_ga.fitness import validate_moveset
from charizard_ga.ga import INDIVIDUAL_CLASS, ensure_deap_types
from charizard_ga.operators import (OperatorCounters, adaptive_mutation_prob, cx_one_point_repair, cx_set,
                                    cx_uniform_repair, mut_replace_one, random_moveset, repair_duplicates,
                                    sel_expected_count, sel_ranking, sel_roulette_safe)


def make(genes, value=None):
    ensure_deap_types()
    ind = getattr(creator, INDIVIDUAL_CLASS)(genes)
    if value is not None:
        ind.fitness.values = (value,)
    return ind


def test_initialization_is_always_valid(catalog):
    random.seed(1)
    for _ in range(2000):
        assert validate_moveset(random_moveset(catalog.ids), catalog)[0]


def test_repair_keeps_unique_genes_and_fills_from_parents(catalog):
    random.seed(3)
    a, b, c, d, e, f, g = catalog.ids[:7]
    child = [a, a, f, g]
    fixed = repair_duplicates(child, [a, b, c, d, e, a, f, g], catalog.ids)
    assert fixed == 1
    assert validate_moveset(child, catalog)[0]
    assert {a, f, g} <= set(child)                       # se conservan los genes validos
    assert set(child) <= {a, b, c, d, e, f, g}            # el relleno proviene de los padres


def test_crossovers_produce_valid_children_with_parent_genes(catalog):
    random.seed(5)
    counters = OperatorCounters()
    for i in range(3000):
        p1 = random_moveset(catalog.ids)
        p2 = random_moveset(catalog.ids)
        if i % 3 == 0:  # fuerza genes compartidos en posiciones distintas
            p2[random.randrange(4)] = p1[random.randrange(4)]
            if len(set(p2)) < 4:
                continue
        union = set(p1) | set(p2)
        c1, c2 = make(list(p1)), make(list(p2))
        if i % 2:
            cx_uniform_repair(c1, c2, 0.5, catalog.ids, counters)
        else:
            cx_one_point_repair(c1, c2, catalog.ids, counters)
        for child in (c1, c2):
            assert validate_moveset(child, catalog)[0]
            assert set(child) <= union
    assert counters.repaired_children > 0  # el escenario de duplicados efectivamente ocurrio


def test_mutation_changes_exactly_one_gene_to_new_move(catalog):
    random.seed(7)
    counters = OperatorCounters()
    for _ in range(2000):
        ind = make(random_moveset(catalog.ids))
        before = list(ind)
        mut_replace_one(ind, catalog.ids, counters)
        diff = [i for i in range(4) if ind[i] != before[i]]
        assert len(diff) == 1
        assert ind[diff[0]] not in before
        assert validate_moveset(ind, catalog)[0]


def test_roulette_handles_zero_total_fitness(catalog):
    random.seed(11)
    pop = [make(random_moveset(catalog.ids), 0.0) for _ in range(10)]
    chosen = sel_roulette_safe(pop, 10)
    assert len(chosen) == 10 and all(c in pop for c in chosen)
    pop2 = [make(random_moveset(catalog.ids), float(i + 1)) for i in range(10)]
    assert len(sel_roulette_safe(pop2, 7)) == 7


def test_set_crossover_keeps_shared_genes_and_never_repeats(catalog):
    random.seed(13)
    counters = OperatorCounters()
    for i in range(3000):
        p1 = random_moveset(catalog.ids)
        p2 = random_moveset(catalog.ids)
        if i % 2 == 0:  # fuerza 1 o 2 genes compartidos en posiciones distintas
            for _ in range(1 + i % 4 // 2):
                p2[random.randrange(4)] = p1[random.randrange(4)]
            if len(set(p2)) < 4:
                continue
        shared, union = set(p1) & set(p2), set(p1) | set(p2)
        c1, c2 = make(list(p1)), make(list(p2))
        cx_set(c1, c2, counters)
        for child in (c1, c2):
            assert validate_moveset(child, catalog)[0]          # nunca repite: no necesita reparacion
            assert shared <= set(child)                         # lo que comparten ambos padres pasa a los dos hijos
            assert set(child) <= union                          # todo el material viene de los padres
    assert counters.crossovers > 0 and counters.repaired_children == 0


def test_positional_crossover_can_lose_shared_genes(catalog):
    # Motivo de la cruza de conjuntos: con la binomial aleatoria un hijo puede perder un gen que tenian ambos padres.
    random.seed(17)
    a, b, c, d, e, f, g = catalog.ids[:7]
    lost = 0
    for _ in range(500):
        c1, c2 = make([a, b, c, d]), make([b, e, f, g])        # comparten 'b' en posiciones distintas
        cx_uniform_repair(c1, c2, 0.5, catalog.ids, OperatorCounters())
        lost += (b not in c1) + (b not in c2)
    assert lost > 0


def test_ranking_selection_depends_on_order_not_on_values(catalog):
    random.seed(19)
    pop = [make(random_moveset(catalog.ids), v) for v in (100.0, 99.0, 98.0, 1.0)]
    counts = Counter(id(ind) for ind in sel_ranking(pop, 40000))
    shares = [counts[id(ind)] / 40000 for ind in pop]
    for got, expected in zip(shares, (4 / 10, 3 / 10, 2 / 10, 1 / 10)):   # pesos 4, 3, 2, 1
        assert got == pytest.approx(expected, abs=0.01)
    assert len(sel_ranking(pop, 7)) == 7


def test_expected_count_selection_follows_the_class_example(catalog):
    # Ejemplo de la teoria (diap. 29-32): aptitudes 61, 11, 33, 25, 44, 15, 17 (promedio 29,43). Las partes enteras
    # de aptitud/promedio aseguran 2 copias de I1, 1 de I3 y 1 de I5; los 3 lugares restantes salen de la ruleta
    # sobre las mantisas.
    random.seed(23)
    pop = [make(random_moveset(catalog.ids), v) for v in (61.0, 11.0, 33.0, 25.0, 44.0, 15.0, 17.0)]
    for _ in range(200):
        chosen = sel_expected_count(pop, 7)
        counts = Counter(id(ind) for ind in chosen)
        assert len(chosen) == 7
        assert counts[id(pop[0])] >= 2 and counts[id(pop[2])] >= 1 and counts[id(pop[4])] >= 1
    zeros = [make(random_moveset(catalog.ids), 0.0) for _ in range(5)]
    assert len(sel_expected_count(zeros, 5)) == 5


def test_adaptive_mutation_rises_when_population_converges():
    diverse = [50.0, 60.0, 70.0, 80.0]          # media/maxima = 0,81 < 0,9 -> probabilidad base
    converged = [79.0, 80.0, 80.0, 80.0]        # media/maxima ~ 0,997 -> cerca del tope
    assert adaptive_mutation_prob(diverse, 0.1, 0.4, 0.9) == pytest.approx(0.1)
    p = adaptive_mutation_prob(converged, 0.1, 0.4, 0.9)
    assert 0.38 < p <= 0.4
    assert adaptive_mutation_prob([80.0] * 4, 0.1, 0.4, 0.9) == pytest.approx(0.4)
