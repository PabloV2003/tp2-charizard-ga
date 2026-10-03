"""Coherencia entre logs, resumenes y comparaciones guardadas en results/ (requiere haber ejecutado el lote)."""
import csv
import json
import math

import pytest

from charizard_ga.config import load_experiments
from charizard_ga.experiments import run_and_save
from charizard_ga.fitness import fitness
from charizard_ga.paths import FIGURES_DIR, RESULTS_DIR

pytestmark = pytest.mark.skipif(not (RESULTS_DIR / "summary_runs.csv").exists(), reason="lote no ejecutado")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_every_run_has_complete_evidence(catalog, experiments):
    rows = read_csv(RESULTS_DIR / "summary_runs.csv")
    assert len(rows) == len(experiments["configs"]) * len(experiments["seeds"])
    for r in rows:
        log = read_csv(RESULTS_DIR / "runs" / r["config_id"] / f"seed_{r['semilla']}_log.csv")
        summary = json.loads((RESULTS_DIR / "runs" / r["config_id"] / f"seed_{r['semilla']}_summary.json").read_text(encoding="utf-8"))
        assert len(log) == 201 and log[0]["generacion"] == "0"
        assert float(log[-1]["mejor_acumulada"]) == float(r["mejor_aptitud"])
        assert max(float(x["aptitud_max"]) for x in log) == float(r["mejor_aptitud"])
        assert summary["dataset_version"] == catalog.dataset_version
        ids = summary["mejor_solucion"]["moveset_ids"]
        w = experiments["profiles"][r["perfil"]]
        assert fitness(ids, catalog, w) == float(r["mejor_aptitud"])   # se recalcula exactamente
        assert summary["mejor_solucion"]["generacion_encontrada"] == int(log[-1]["generacion_mejor_acumulada"])


def test_main_runs_are_seed_42_of_r1_to_r5():
    rows = [r for r in read_csv(RESULTS_DIR / "summary_runs.csv") if r["corrida_principal"] == "True"]
    assert sorted(r["config_id"] for r in rows) == ["R1", "R2", "R3", "R4", "R5"]
    assert {r["semilla"] for r in rows} == {"42"}


def test_saved_main_run_is_reproducible(tmp_path, catalog, experiments):
    exp = next(c for c in experiments["configs"] if c.config_id == "R1")
    new = run_and_save(exp, 42, catalog, experiments["profiles"]["R1"], tmp_path, is_main=True, replica=1)
    assert read_csv(new["_log_path"]) == read_csv(RESULTS_DIR / "runs" / "R1" / "seed_42_log.csv")


def test_ga_never_exceeds_exhaustive_optimum():
    for g in read_csv(RESULTS_DIR / "ga_vs_optimum.csv"):
        assert float(g["mejor_aptitud"]) <= float(g["optimo"]) + 1e-9


def test_config_summary_matches_runs(experiments):
    runs = read_csv(RESULTS_DIR / "summary_runs.csv")
    for agg in read_csv(RESULTS_DIR / "summary_configs.csv"):
        vals = [float(r["mejor_aptitud"]) for r in runs if r["config_id"] == agg["config_id"]]
        assert math.isclose(float(agg["aptitud_media"]), sum(vals) / len(vals), abs_tol=1e-9)
        assert float(agg["aptitud_max"]) == max(vals) and float(agg["aptitud_min"]) == min(vals)


def test_main_figures_exist():
    if not FIGURES_DIR.exists():
        pytest.skip("figuras no generadas")
    for cid in ("R1", "R2", "R3", "R4", "R5"):
        assert (FIGURES_DIR / "runs" / f"{cid}_seed42.png").exists()
