"""Pruebas de la funcion de aptitud contra un caso calculado de forma independiente."""
import itertools
import math

import pytest

from charizard_ga.fitness import (Evaluator, Weights, components, contributions, fitness, partial_components,
                                  validate_moveset, weighted_fitness)

EXAMPLE = ["flamethrower", "air-slash", "dragon-pulse", "solar-beam"]  # ejemplo de la entrega parcial


def ids(catalog, slugs):
    return [catalog.by_slug(s) for s in slugs]


def test_example_components_hand_computed(catalog):
    # Calculo manual independiente:
    #  Lanzallamas (Fuego 90/100), Tajo Aereo (Volador 75/95), Pulso Dragon (Dragon 85/100), Rayo Solar (Planta 120/100)
    #  Cobertura: Fuego{Planta,Hielo,Bicho,Acero} U Volador{Planta,Lucha,Bicho} U Dragon{Dragon} U Planta{Agua,Tierra,Roca}
    #             = 9 tipos -> C = 9/18 = 0.5
    #  P = ((90+75+85+120)/4)/150 = 92.5/150 ; A = ((100+95+100+100)/4)/100 = 0.9875 ; S = 2/4 ; D = 4/4
    comp = components(ids(catalog, EXAMPLE), catalog)
    assert comp.C == pytest.approx(0.5)
    assert comp.P == pytest.approx(92.5 / 150)
    assert comp.A == pytest.approx(0.9875)
    assert comp.S == pytest.approx(0.5)
    assert comp.D == pytest.approx(1.0)
    assert set(comp.covered) == {"grass", "ice", "bug", "steel", "fighting", "dragon", "water", "ground", "rock"}
    assert len(comp.covered) + len(comp.uncovered) == 18


def test_example_fitness_base_profile(catalog, base_weights):
    expected = 100 * (0.40 * 0.5 + 0.20 * (92.5 / 150) + 0.15 * 0.9875 + 0.15 * 0.5 + 0.10 * 1.0)
    assert expected == pytest.approx(64.6458333333, abs=1e-9)
    assert fitness(ids(catalog, EXAMPLE), catalog, base_weights) == pytest.approx(expected, abs=1e-12)
    contrib = contributions(components(ids(catalog, EXAMPLE), catalog), base_weights)
    assert sum(contrib.values()) == pytest.approx(expected, abs=1e-12)


def test_invalid_individuals_get_zero(catalog, base_weights):
    a, b, c, d = ids(catalog, EXAMPLE)
    status_move = 14  # Danza Espada: aprendible pero excluida (movimiento de estado)
    assert status_move not in catalog.moves
    cases = {
        "longitud 3": [a, b, c],
        "longitud 5": [a, b, c, d, catalog.by_slug("earthquake")],
        "repetidos": [a, a, b, c],
        "id no permitido": [a, b, c, status_move],
        "id inexistente": [a, b, c, 999999],
        "vacio": [],
    }
    for label, ms in cases.items():
        ok, _ = validate_moveset(ms, catalog)
        assert not ok, label
        assert fitness(ms, catalog, base_weights) == 0.0, label


def test_same_type_different_moves_is_valid(catalog, base_weights):
    ms = ids(catalog, ["flamethrower", "fire-blast", "heat-wave", "overheat"])
    assert validate_moveset(ms, catalog)[0]
    comp = components(ms, catalog)
    assert comp.D == pytest.approx(0.25) and comp.S == pytest.approx(1.0)


def test_permutation_invariance(catalog, experiments):
    ms = ids(catalog, ["earthquake", "hurricane", "focus-blast", "flare-blitz"])
    for w in experiments["profiles"].values():
        values = {fitness(list(p), catalog, w) for p in itertools.permutations(ms)}
        assert len(values) == 1


def test_weights_must_be_valid():
    with pytest.raises(ValueError):
        Weights(0.5, 0.5, 0.1, 0.0, 0.0)   # suma 1.1
    with pytest.raises(ValueError):
        Weights(1.2, -0.2, 0.0, 0.0, 0.0)  # negativo
    for profile in ((0.40, 0.20, 0.15, 0.15, 0.10), (0.60, 0.15, 0.10, 0.05, 0.10), (0.20, 0.45, 0.15, 0.10, 0.10),
                    (0.25, 0.15, 0.40, 0.10, 0.10), (0.25, 0.15, 0.10, 0.30, 0.20)):
        Weights(*profile)


def test_components_in_unit_interval(catalog):
    for combo in itertools.islice(itertools.combinations(catalog.ids, 4), 0, 300000, 997):
        for value in components(combo, catalog).as_tuple():
            assert 0.0 <= value <= 1.0


def test_cache_is_isolated_per_weights(catalog, experiments):
    ms = ids(catalog, ["earthquake", "hurricane", "focus-blast", "flare-blitz"])
    ev1 = Evaluator(catalog, experiments["profiles"]["R1"])
    ev3 = Evaluator(catalog, experiments["profiles"]["R3"])
    v1, v3 = ev1.value(ms), ev3.value(ms)
    assert v1 != v3
    assert ev1.value(list(reversed(ms))) == v1           # acierto de cache con otro orden
    assert ev1.requested == 2 and ev1.effective == 1
    assert v1 == fitness(ms, catalog, experiments["profiles"]["R1"])


def test_partial_components_match_full_at_four(catalog, base_weights):
    ms = ids(catalog, EXAMPLE)
    full = components(ms, catalog).as_tuple()
    assert all(math.isclose(a, b, abs_tol=1e-15) for a, b in zip(partial_components(ms, catalog), full))
    assert weighted_fitness(components(ms, catalog), base_weights) == pytest.approx(
        100 * sum(w * c for w, c in zip(base_weights.as_tuple(), partial_components(ms, catalog))))
