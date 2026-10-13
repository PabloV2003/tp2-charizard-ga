"""Lectura y validacion de las configuraciones (parametros del AG, perfiles de pesos y semillas)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .fitness import FITNESS_VERSIONS, Weights
from .paths import CONFIG_DIR

SELECTIONS = ("tournament", "roulette", "ranking", "expected_count")
CROSSOVERS = ("set", "uniform", "one_point")
MUTATION_MODES = ("simple", "adaptive")
STOP_CRITERIA = ("generations", "stagnation")


@dataclass(frozen=True)
class GAConfig:
    """Parametros del algoritmo genetico."""

    population_size: int = 100
    generations: int = 200            # generaciones evolutivas (ademas de la generacion 0); tope si hay estancamiento
    selection: str = "tournament"     # "tournament", "roulette", "ranking" o "expected_count" (control sobre numero esperado)
    tournament_size: int = 3
    crossover: str = "set"            # "set" (conjuntos), "uniform" (binomial aleatoria) o "one_point" (simple)
    cx_prob: float = 0.8              # probabilidad de cruza POR PAREJA
    cx_indpb: float = 0.5             # probabilidad de intercambio POR GEN (solo cruza uniforme)
    mutation_prob: float = 0.1        # probabilidad de mutacion POR INDIVIDUO (reemplaza 1 gen); base si es adaptativa
    mutation_mode: str = "simple"     # "simple" (constante) o "adaptive" (adaptativa por convergencia)
    mutation_prob_max: float = 0.4    # tope de la mutacion adaptativa
    convergence_threshold: float = 0.9  # media/maxima a partir de la cual la mutacion adaptativa empieza a subir
    elitism: int = 2                  # cantidad de mejores individuos copiados sin cambios
    stop_criterion: str = "generations"  # "generations" o "stagnation" (sin mejora durante `patience` generaciones)
    patience: int = 30                # generaciones sin mejora para el paro por estancamiento
    fitness_version: str = "F2"       # version de la funcion de aptitud (ver fitness.FITNESS_VERSIONS)

    def __post_init__(self):
        if self.selection not in SELECTIONS:
            raise ValueError(f"Seleccion desconocida: {self.selection}")
        if self.crossover not in CROSSOVERS:
            raise ValueError(f"Cruza desconocida: {self.crossover}")
        if self.mutation_mode not in MUTATION_MODES:
            raise ValueError(f"Mutacion desconocida: {self.mutation_mode}")
        if not all(0 <= p <= 1 for p in (self.cx_prob, self.cx_indpb, self.mutation_prob, self.mutation_prob_max)):
            raise ValueError("Las probabilidades deben estar en [0, 1]")
        if self.mutation_mode == "adaptive" and self.mutation_prob_max < self.mutation_prob:
            raise ValueError("El tope de la mutacion adaptativa no puede ser menor que la probabilidad base")
        if not (0 <= self.convergence_threshold < 1):
            raise ValueError("El umbral de convergencia debe estar en [0, 1)")
        if self.population_size < 2 or self.generations < 0:
            raise ValueError("Poblacion o generaciones invalidas")
        if not (0 <= self.elitism < self.population_size):
            raise ValueError("El elitismo debe ser menor que el tamano de poblacion")
        if self.tournament_size < 1:
            raise ValueError("El tamano de torneo debe ser >= 1")
        if self.stop_criterion not in STOP_CRITERIA:
            raise ValueError(f"Criterio de paro desconocido: {self.stop_criterion}")
        if self.patience < 1:
            raise ValueError("La paciencia del paro por estancamiento debe ser >= 1")
        if self.fitness_version not in FITNESS_VERSIONS:
            raise ValueError(f"Version de aptitud desconocida: {self.fitness_version}")

    def to_dict(self) -> dict:
        return asdict(self)

    def with_overrides(self, overrides: dict) -> "GAConfig":
        return replace(self, **overrides)


@dataclass(frozen=True)
class ExperimentConfig:
    """Una configuracion experimental: identificador, perfil de pesos y parametros del AG."""

    config_id: str
    grupo: str
    profile: str
    profile_name: str
    descripcion: str
    weights: Weights
    ga: GAConfig
    overrides: dict


def load_experiments(path: Path | None = None) -> dict:
    """Devuelve {'base_profile', 'profiles', 'seeds', 'main_seed', 'configs': [ExperimentConfig], 'raw'}."""
    path = Path(path) if path else CONFIG_DIR / "experiments.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = GAConfig(**raw["ga_base"])
    profiles = {pid: Weights.from_dict(p) for pid, p in raw["profiles"].items()}
    configs = []
    for c in raw["configs"]:
        configs.append(ExperimentConfig(
            config_id=c["id"], grupo=c["grupo"], profile=c["profile"],
            profile_name=raw["profiles"][c["profile"]]["nombre"], descripcion=c["descripcion"],
            weights=profiles[c["profile"]], ga=base.with_overrides(c.get("overrides", {})),
            overrides=c.get("overrides", {}),
        ))
    ids = [c.config_id for c in configs]
    if len(ids) != len(set(ids)):
        raise ValueError("Identificadores de configuracion repetidos")
    return {
        "base_profile": raw["base_profile"],
        "profiles": profiles,
        "profile_info": raw["profiles"],
        "seeds": list(raw["seeds"]),
        "main_seed": raw["main_seed"],
        "ga_base": base,
        "configs": configs,
        "raw": raw,
    }


def load_quality_criterion(path: Path | None = None) -> dict:
    path = Path(path) if path else CONFIG_DIR / "quality_criterion.json"
    return json.loads(path.read_text(encoding="utf-8"))
