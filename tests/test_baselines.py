"""Pruebas de los metodos de comparacion."""
import itertools
import math

import pytest

from charizard_ga.baselines import exhaustive_optimum, exhaustive_table, greedy, local_search, random_search
from charizard_ga.fitness import fitness


def test_exhaustive_on_subset_matches_bruteforce(catalog, base_weights):
    subset = catalog.ids[:14]
    table = exhaustive_table(catalog, subset)
    assert table.n == math.comb(14, 4)
    res = exhaustive_optimum(table, base_weights)
    brute = max(fitness(c, catalog, base_weights) for c in itertools.combinations(subset, 4))
    assert res["optimo"] == pytest.approx(brute, abs=1e-12)
    assert all(fitness(k, catalog, base_weights) == pytest.approx(brute, abs=1e-9) for k in res["movesets_optimos"])


def test_random_search_is_reproducible_and_valid(catalog, base_weights):
    a = random_search(catalog, base_weights, 500, seed=42)
    b = random_search(catalog, base_weights, 500, seed=42)
    assert a["mejor_moveset"] == b["mejor_moveset"] and a["mejor_aptitud"] == b["mejor_aptitud"]
    assert a["evaluaciones_solicitadas"] == 500
    c = random_search(catalog, base_weights, 300, seed=42, budget_mode="effective")
    assert c["evaluaciones_efectivas"] == 300


def test_greedy_and_local_search(catalog, base_weights):
    g = greedy(catalog, base_weights)
    assert len(set(g["mejor_moveset"])) == 4
    assert g["mejor_aptitud"] == pytest.approx(fitness(g["mejor_moveset"], catalog, base_weights))
    ls = local_search(catalog, base_weights, g["mejor_moveset"])
    assert ls["mejor_aptitud"] >= g["mejor_aptitud"]


def test_exhaustive_optimum_f1_vs_f2(catalog, base_weights):
    # La version original (F1) premia ataques trampa; con potencia efectiva (F2) el optimo cambia.
    names = lambda key: {catalog.moves[m].slug for m in key}  # noqa: E731
    f1 = exhaustive_optimum(exhaustive_table(catalog, version="F1"), base_weights)
    f2 = exhaustive_optimum(exhaustive_table(catalog, version="F2"), base_weights)
    assert names(f1["movesets_optimos"][0]) == {"fly", "solar-beam", "earthquake", "focus-punch"}
    assert names(f2["movesets_optimos"][0]) == {"earthquake", "fire-blast", "focus-blast", "hurricane"}
    assert f1["n_empates_optimo"] == 1 and f2["n_empates_optimo"] == 1
