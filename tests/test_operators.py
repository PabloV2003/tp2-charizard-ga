"""Pruebas de inicializacion, cruza + reparacion, mutacion y seleccion."""
import random

from deap import creator

from charizard_ga.fitness import validate_moveset
from charizard_ga.ga import INDIVIDUAL_CLASS, ensure_deap_types
from charizard_ga.operators import (OperatorCounters, cx_one_point_repair, cx_uniform_repair, mut_replace_one,
                                    random_moveset, repair_duplicates, sel_roulette_safe)


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
