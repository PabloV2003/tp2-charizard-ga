"""Pruebas del ciclo evolutivo: tamano constante, elitismo, mejor acumulada y reproducibilidad."""
import warnings

import pytest

from charizard_ga.config import GAConfig
from charizard_ga.fitness import fitness, validate_moveset
from charizard_ga.ga import ensure_deap_types, run_ga

SMALL = GAConfig(population_size=30, generations=25)


@pytest.mark.parametrize("cfg", [
    SMALL,
    GAConfig(population_size=30, generations=25, selection="roulette"),
    GAConfig(population_size=31, generations=25, crossover="one_point", elitism=1),
    GAConfig(population_size=30, generations=25, mutation_prob=0.5, elitism=0),
])
def test_population_and_best_invariants(catalog, base_weights, cfg):
    res = run_ga(catalog, base_weights, cfg, seed=123)
    assert len(res.log) == cfg.generations + 1                      # generacion 0 incluida
    prev_best = -1.0
    for row in res.log:
        assert row["tam_poblacion"] == cfg.population_size           # tamano constante
        assert row["individuos_invalidos"] == 0
        assert row["mejor_acumulada"] >= row["aptitud_max"] - 1e-12  # mejor acumulada >= mejor de la generacion
        assert row["mejor_acumulada"] >= prev_best - 1e-12          # no decrece
        prev_best = row["mejor_acumulada"]
    if cfg.elitism > 0:
        maxima = [row["aptitud_max"] for row in res.log]
        assert all(b >= a - 1e-12 for a, b in zip(maxima, maxima[1:]))  # las elites protegen al maximo
    assert validate_moveset(res.best_moveset, catalog)[0]
    assert fitness(res.best_moveset, catalog, base_weights) == pytest.approx(res.best_fitness, abs=1e-12)
    assert res.best_fitness == pytest.approx(max(r["aptitud_max"] for r in res.log), abs=1e-12)


def test_same_seed_same_results_excluding_time(catalog, base_weights):
    r1 = run_ga(catalog, base_weights, SMALL, seed=99)
    r2 = run_ga(catalog, base_weights, SMALL, seed=99)
    assert r1.log == r2.log
    assert r1.best_moveset == r2.best_moveset and r1.best_generation == r2.best_generation
    r3 = run_ga(catalog, base_weights, SMALL, seed=100)
    assert r3.log != r1.log


def test_deap_types_can_be_recreated_without_warnings(catalog, base_weights):
    with warnings.catch_warnings():
        warnings.simplefilter("error")      # cualquier advertencia de DEAP haria fallar la prueba
        ensure_deap_types()
        ensure_deap_types()
        run_ga(catalog, base_weights, GAConfig(population_size=10, generations=2), seed=1)


def test_invalid_config_is_rejected():
    with pytest.raises(ValueError):
        GAConfig(selection="ranking")
    with pytest.raises(ValueError):
        GAConfig(elitism=100, population_size=100)
    with pytest.raises(ValueError):
        GAConfig(stop_criterion="stagnation")
