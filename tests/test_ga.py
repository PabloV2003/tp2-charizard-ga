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
    GAConfig(population_size=30, generations=25, crossover="uniform", fitness_version="F1"),
    GAConfig(population_size=30, generations=25, selection="ranking"),
    GAConfig(population_size=31, generations=25, selection="expected_count"),
    GAConfig(population_size=30, generations=25, mutation_mode="adaptive"),
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
    assert fitness(res.best_moveset, catalog, base_weights, cfg.fitness_version) == pytest.approx(res.best_fitness, abs=1e-12)
    assert all(row["prob_mutacion"] is None for row in res.log[:1])
    if cfg.mutation_mode == "adaptive":
        assert all(cfg.mutation_prob <= row["prob_mutacion"] <= cfg.mutation_prob_max for row in res.log[1:])
    else:
        assert all(row["prob_mutacion"] == cfg.mutation_prob for row in res.log[1:])
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


def test_stagnation_stops_after_patience_without_improvement(catalog, base_weights):
    cfg = GAConfig(population_size=30, generations=200, stop_criterion="stagnation", patience=15)
    res = run_ga(catalog, base_weights, cfg, seed=7)
    assert res.generations_executed < cfg.generations
    assert len(res.log) == res.generations_executed + 1
    assert res.generations_executed - res.best_generation == cfg.patience
    assert "estancamiento" in res.stop_reason
    full = run_ga(catalog, base_weights, GAConfig(population_size=30, generations=200), seed=7)
    assert full.log[:len(res.log)] == res.log            # mismas generaciones hasta el corte (misma semilla)


def test_invalid_config_is_rejected():
    with pytest.raises(ValueError):
        GAConfig(selection="inexistente")
    with pytest.raises(ValueError):
        GAConfig(crossover="inexistente")
    with pytest.raises(ValueError):
        GAConfig(elitism=100, population_size=100)
    with pytest.raises(ValueError):
        GAConfig(stop_criterion="inexistente")
    with pytest.raises(ValueError):
        GAConfig(mutation_mode="inexistente")
    with pytest.raises(ValueError):
        GAConfig(mutation_mode="adaptive", mutation_prob=0.5, mutation_prob_max=0.4)
    with pytest.raises(ValueError):
        GAConfig(fitness_version="F9")
