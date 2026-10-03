"""Comparacion con otros metodos y analisis de brecha del AG (mismo catalogo, misma funcion de aptitud).

Requiere haber ejecutado antes scripts/run_experiments.py (usa sus presupuestos y resultados).

Salidas en results/baselines/ y results/:
    exhaustive_optimum.csv          optimo exacto por perfil (catalogo completo), empates y costo
    exhaustive_top10.csv            10 mejores combinaciones por perfil
    conservative_optimum.csv        optimo restringido al subconjunto conservador (sensibilidad del catalogo)
    random_search.csv               busqueda aleatoria con presupuesto igualado al del AG (2 modos)
    random_search_curves_R1.csv     mejor acumulada vs evaluaciones (perfil base)
    greedy.csv                      heuristica voraz y voraz + busqueda local
    method_comparison.csv           resumen por metodo y perfil
    ../ga_vs_optimum.csv            brecha de cada corrida del AG respecto del optimo
    ../quality_assessment.csv       criterio de calidad por configuracion
    ../cross_profile_matrix.csv     aptitud de cada solucion principal bajo los cinco perfiles
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charizard_ga.baselines import (TOL, exhaustive_optimum, exhaustive_table, greedy, local_search,  # noqa: E402
                                    random_search, rank_of)
from charizard_ga.config import load_experiments, load_quality_criterion  # noqa: E402
from charizard_ga.data import load_catalog  # noqa: E402
from charizard_ga.fitness import components, weighted_fitness  # noqa: E402
from charizard_ga.io_utils import write_json, write_rows_csv  # noqa: E402
from charizard_ga.paths import RESULTS_DIR  # noqa: E402

OUT = RESULTS_DIR / "baselines"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def slugs(catalog, key) -> str:
    return "|".join(catalog.moves[m].slug for m in key)


def names_es(catalog, key) -> str:
    return " | ".join(catalog.moves[m].nombre_es for m in key)


def key_from_slugs(catalog, text: str) -> tuple:
    return tuple(sorted(catalog.by_slug(s) for s in text.split("|")))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    catalog = load_catalog()
    exps = load_experiments()
    quality = load_quality_criterion()
    profiles = exps["profiles"]
    base_w = profiles[exps["base_profile"]]
    runs = read_csv(RESULTS_DIR / "summary_runs.csv")
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) Enumeracion exhaustiva del catalogo completo ------------------------------------------
    table = exhaustive_table(catalog)
    assert table.n == math.comb(catalog.M, 4)
    print(f"Exhaustiva: {table.n:,} combinaciones; enumeracion + componentes en {table.seconds:.2f} s")
    optima, opt_rows, top_rows, fit_arrays = {}, [], [], {}
    for pid, w in profiles.items():
        res = exhaustive_optimum(table, w)
        optima[pid] = res["optimo"]
        fit_arrays[pid] = res["fitness_array"]
        best_key = res["movesets_optimos"][0]
        comp = components(best_key, catalog)
        opt_rows.append({
            "perfil": pid, "optimo": res["optimo"], "n_empates_optimo": res["n_empates_optimo"],
            "movesets_optimos": " || ".join(slugs(catalog, k) for k in res["movesets_optimos"]),
            "movesets_optimos_es": " || ".join(names_es(catalog, k) for k in res["movesets_optimos"]),
            "C": comp.C, "P": comp.P, "A": comp.A, "S": comp.S, "D": comp.D,
            "n_tipos_cubiertos": len(comp.covered), "tipos_no_cubiertos": "|".join(comp.uncovered),
            "aptitud_perfil_base": weighted_fitness(comp, base_w),
            "combinaciones_evaluadas": table.n, "segundos_enumeracion_componentes": table.seconds,
            "segundos_puntuacion_perfil": res["segundos_puntuacion"],
        })
        for rank, (k, v) in enumerate(res["top"], start=1):
            top_rows.append({"perfil": pid, "puesto_orden": rank, "aptitud": v, "moveset": slugs(catalog, k),
                             "moveset_es": names_es(catalog, k)})
        print(f"  {pid}: optimo {res['optimo']:.6f} ({res['n_empates_optimo']} empate/s) -> {slugs(catalog, best_key)}")
    write_rows_csv(OUT / "exhaustive_optimum.csv", opt_rows, list(opt_rows[0].keys()))
    # Histograma de la aptitud de TODAS las combinaciones (para graficar sin recalcular).
    hist_rows = []
    for pid, fit in fit_arrays.items():
        lo, hi = math.floor(fit.min()), math.ceil(fit.max())
        edges = np.arange(lo, hi + 0.25, 0.25)
        counts, edges = np.histogram(fit, bins=edges)
        for c, a, b in zip(counts, edges[:-1], edges[1:]):
            hist_rows.append({"perfil": pid, "desde": float(a), "hasta": float(b), "combinaciones": int(c)})
    write_rows_csv(OUT / "exhaustive_histogram.csv", hist_rows, ["perfil", "desde", "hasta", "combinaciones"])
    write_rows_csv(OUT / "exhaustive_top10.csv", top_rows, list(top_rows[0].keys()))

    # 2) Sensibilidad del catalogo: optimo restringido al subconjunto conservador ---------------
    #    Misma funcion (incluida la normalizacion P con la potencia maxima del catalogo completo);
    #    solo se restringe el conjunto factible a movimientos sin carga, recarga ni fallo condicional.
    cons_ids = [m for m in catalog.ids if catalog.moves[m].subconjunto_conservador]
    cons_table = exhaustive_table(catalog, cons_ids)
    cons_rows = []
    for pid, w in profiles.items():
        res = exhaustive_optimum(cons_table, w)
        k = res["movesets_optimos"][0]
        comp = components(k, catalog)
        cons_rows.append({
            "perfil": pid, "M_subconjunto": len(cons_ids), "combinaciones": cons_table.n,
            "optimo_restringido": res["optimo"], "optimo_catalogo_completo": optima[pid],
            "diferencia": optima[pid] - res["optimo"], "n_empates": res["n_empates_optimo"],
            "movesets_optimos": " || ".join(slugs(catalog, x) for x in res["movesets_optimos"]),
            "movesets_optimos_es": " || ".join(names_es(catalog, x) for x in res["movesets_optimos"]),
            "C": comp.C, "P": comp.P, "A": comp.A, "S": comp.S, "D": comp.D, "n_tipos_cubiertos": len(comp.covered),
            "tipos_no_cubiertos": "|".join(comp.uncovered), "aptitud_perfil_base": weighted_fitness(comp, base_w),
            "puesto_en_catalogo_completo": rank_of(table, fit_arrays[pid], res["optimo"]),
            "segundos": cons_table.seconds + res["segundos_puntuacion"],
        })
        print(f"  conservador {pid}: {res['optimo']:.6f} -> {slugs(catalog, k)}")
    write_rows_csv(OUT / "conservative_optimum.csv", cons_rows, list(cons_rows[0].keys()))

    # 3) Brecha del AG respecto del optimo ------------------------------------------------------
    gap_rows = []
    for r in runs:
        pid = r["perfil"]
        val = float(r["mejor_aptitud"])
        opt = optima[pid]
        log = read_csv(RESULTS_DIR / "runs" / r["config_id"] / f"seed_{r['semilla']}_log.csv")
        hit_row = next((row for row in log if float(row["mejor_acumulada"]) >= opt - TOL), None)
        gap_rows.append({
            "config_id": r["config_id"], "grupo": r["grupo"], "perfil": pid, "semilla": r["semilla"],
            "corrida_principal": r["corrida_principal"], "mejor_aptitud": val, "optimo": opt,
            "brecha_absoluta": opt - val, "brecha_relativa": (opt - val) / opt,
            "alcanza_optimo": abs(opt - val) < TOL,
            "puesto_en_exhaustiva": rank_of(table, fit_arrays[pid], val),
            "generacion_alcanza_optimo": int(hit_row["generacion"]) if hit_row else "",
            "efectivas_hasta_optimo": int(hit_row["evaluaciones_efectivas_acum"]) if hit_row else "",
            "solicitadas_hasta_optimo": int(hit_row["evaluaciones_solicitadas_acum"]) if hit_row else "",
            "evaluaciones_efectivas_total": int(r["evaluaciones_efectivas"]),
            "fraccion_espacio_evaluada": int(r["evaluaciones_efectivas"]) / table.n,
        })
    write_rows_csv(RESULTS_DIR / "ga_vs_optimum.csv", gap_rows, list(gap_rows[0].keys()))

    q_rows = []
    for exp in exps["configs"]:
        rs = [g for g in gap_rows if g["config_id"] == exp.config_id]
        hits = sum(1 for g in rs if g["alcanza_optimo"])
        mean_rel = statistics.fmean(g["brecha_relativa"] for g in rs)
        q_rows.append({
            "config_id": exp.config_id, "perfil": exp.profile, "replicas": len(rs), "replicas_alcanzan_optimo": hits,
            "brecha_relativa_media": mean_rel, "brecha_relativa_max": max(g["brecha_relativa"] for g in rs),
            "corridas_aceptables": sum(1 for g in rs if g["brecha_relativa"] <= quality["umbral_brecha_relativa"]),
            "configuracion_satisfactoria": hits >= quality["umbral_replicas_optimo"] and mean_rel <= quality["umbral_brecha_relativa"],
            "generacion_alcanza_optimo_media": statistics.fmean(g["generacion_alcanza_optimo"] for g in rs) if hits == len(rs) else "",
            "efectivas_hasta_optimo_media": statistics.fmean(g["efectivas_hasta_optimo"] for g in rs) if hits == len(rs) else "",
        })
    write_rows_csv(RESULTS_DIR / "quality_assessment.csv", q_rows, list(q_rows[0].keys()))

    # 4) Matriz de aptitud cruzada: cada solucion principal evaluada con los cinco perfiles ------
    cross_rows = []
    for r in runs:
        if r["corrida_principal"] != "True":
            continue
        key = key_from_slugs(catalog, r["moveset_slugs"])
        comp = components(key, catalog)
        row = {"solucion_de": r["config_id"], "moveset": r["moveset_slugs"]}
        for pid, w in profiles.items():
            row[f"aptitud_{pid}"] = weighted_fitness(comp, w)
            row[f"optimo_{pid}"] = optima[pid]
        cross_rows.append(row)
    write_rows_csv(RESULTS_DIR / "cross_profile_matrix.csv", cross_rows, list(cross_rows[0].keys()))

    # 5) Busqueda aleatoria con presupuesto igualado (por perfil y semilla) ---------------------
    rs_rows, curve_rows = [], []
    for pid, w in profiles.items():
        for r in [x for x in runs if x["config_id"] == pid]:
            seed = int(r["semilla"])
            for mode, budget in (("requested", int(r["evaluaciones_solicitadas"])), ("effective", int(r["evaluaciones_efectivas"]))):
                res = random_search(catalog, w, budget, seed, budget_mode=mode, record_curve=(pid == "R1"))
                rs_rows.append({
                    "perfil": pid, "semilla": seed, "modo_presupuesto": mode, "presupuesto": budget,
                    "mejor_aptitud": res["mejor_aptitud"], "optimo": optima[pid],
                    "brecha_relativa": (optima[pid] - res["mejor_aptitud"]) / optima[pid],
                    "alcanza_optimo": abs(optima[pid] - res["mejor_aptitud"]) < TOL,
                    "puesto_en_exhaustiva": rank_of(table, fit_arrays[pid], res["mejor_aptitud"]),
                    "mejor_moveset": slugs(catalog, res["mejor_moveset"]),
                    "evaluaciones_solicitadas": res["evaluaciones_solicitadas"],
                    "evaluaciones_efectivas": res["evaluaciones_efectivas"], "segundos": res["segundos"],
                })
                if pid == "R1" and mode == "requested":
                    # Se guardan puntos cada 50 evaluaciones efectivas para graficar la convergencia.
                    last_saved = -1
                    for eff, req, best in res["curva"]:
                        if eff // 50 != last_saved or eff == res["evaluaciones_efectivas"]:
                            curve_rows.append({"semilla": seed, "evaluaciones_efectivas": eff, "evaluaciones_solicitadas": req,
                                               "mejor_acumulada": best})
                            last_saved = eff // 50
        print(f"  busqueda aleatoria {pid}: listo")
    write_rows_csv(OUT / "random_search.csv", rs_rows, list(rs_rows[0].keys()))
    write_rows_csv(OUT / "random_search_curves_R1.csv", curve_rows, list(curve_rows[0].keys()))

    # 6) Heuristica voraz y voraz + busqueda local ----------------------------------------------
    g_rows = []
    for pid, w in profiles.items():
        g = greedy(catalog, w)
        ls = local_search(catalog, w, g["mejor_moveset"])
        for res, evals_req, evals_eff, secs in (
            (g, g["evaluaciones_solicitadas"], g["evaluaciones_efectivas"], g["segundos"]),
            (ls, g["evaluaciones_solicitadas"] + ls["evaluaciones_solicitadas"],
             g["evaluaciones_efectivas"] + ls["evaluaciones_efectivas"], g["segundos"] + ls["segundos"]),
        ):
            g_rows.append({
                "perfil": pid, "metodo": res["metodo"], "mejor_aptitud": res["mejor_aptitud"], "optimo": optima[pid],
                "brecha_relativa": (optima[pid] - res["mejor_aptitud"]) / optima[pid],
                "alcanza_optimo": abs(optima[pid] - res["mejor_aptitud"]) < TOL,
                "puesto_en_exhaustiva": rank_of(table, fit_arrays[pid], res["mejor_aptitud"]),
                "mejor_moveset": slugs(catalog, res["mejor_moveset"]), "mejor_moveset_es": names_es(catalog, res["mejor_moveset"]),
                "evaluaciones_solicitadas": evals_req, "evaluaciones_efectivas": evals_eff, "segundos": secs,
                "detalle": "; ".join(f"{s}:{v:.4f}" for s, v in res.get("pasos", [])) or f"iteraciones={res.get('iteraciones')}",
            })
        print(f"  voraz {pid}: {g['mejor_aptitud']:.4f} | +LS {ls['mejor_aptitud']:.4f} (optimo {optima[pid]:.4f})")
    write_rows_csv(OUT / "greedy.csv", g_rows, list(g_rows[0].keys()))

    # 7) Resumen por metodo y perfil --------------------------------------------------------------
    comp_rows = []
    for pid in profiles:
        ga = [g for g in gap_rows if g["config_id"] == pid]
        ga_runs = [r for r in runs if r["config_id"] == pid]
        comp_rows.append({
            "perfil": pid, "metodo": "AG (10 semillas)", "aptitud_media": statistics.fmean(g["mejor_aptitud"] for g in ga),
            "aptitud_min": min(g["mejor_aptitud"] for g in ga), "aptitud_max": max(g["mejor_aptitud"] for g in ga),
            "replicas_alcanzan_optimo": sum(g["alcanza_optimo"] for g in ga), "replicas": len(ga),
            "evaluaciones_solicitadas_media": statistics.fmean(int(r["evaluaciones_solicitadas"]) for r in ga_runs),
            "evaluaciones_efectivas_media": statistics.fmean(int(r["evaluaciones_efectivas"]) for r in ga_runs),
            "segundos_medios": statistics.fmean(float(r["tiempo_segundos"]) for r in ga_runs),
        })
        for mode, label in (("requested", "Busqueda aleatoria (mismas solicitadas)"), ("effective", "Busqueda aleatoria (mismas efectivas)")):
            rr = [x for x in rs_rows if x["perfil"] == pid and x["modo_presupuesto"] == mode]
            comp_rows.append({
                "perfil": pid, "metodo": label, "aptitud_media": statistics.fmean(x["mejor_aptitud"] for x in rr),
                "aptitud_min": min(x["mejor_aptitud"] for x in rr), "aptitud_max": max(x["mejor_aptitud"] for x in rr),
                "replicas_alcanzan_optimo": sum(x["alcanza_optimo"] for x in rr), "replicas": len(rr),
                "evaluaciones_solicitadas_media": statistics.fmean(x["evaluaciones_solicitadas"] for x in rr),
                "evaluaciones_efectivas_media": statistics.fmean(x["evaluaciones_efectivas"] for x in rr),
                "segundos_medios": statistics.fmean(x["segundos"] for x in rr),
            })
        for gr in [x for x in g_rows if x["perfil"] == pid]:
            comp_rows.append({
                "perfil": pid, "metodo": "Voraz" if gr["metodo"] == "voraz" else "Voraz + busqueda local",
                "aptitud_media": gr["mejor_aptitud"], "aptitud_min": gr["mejor_aptitud"], "aptitud_max": gr["mejor_aptitud"],
                "replicas_alcanzan_optimo": int(gr["alcanza_optimo"]), "replicas": 1,
                "evaluaciones_solicitadas_media": gr["evaluaciones_solicitadas"], "evaluaciones_efectivas_media": gr["evaluaciones_efectivas"],
                "segundos_medios": gr["segundos"],
            })
        opt = next(o for o in opt_rows if o["perfil"] == pid)
        comp_rows.append({
            "perfil": pid, "metodo": "Enumeracion exhaustiva", "aptitud_media": opt["optimo"], "aptitud_min": opt["optimo"],
            "aptitud_max": opt["optimo"], "replicas_alcanzan_optimo": 1, "replicas": 1,
            "evaluaciones_solicitadas_media": table.n, "evaluaciones_efectivas_media": table.n,
            "segundos_medios": table.seconds + opt["segundos_puntuacion_perfil"],
        })
    write_rows_csv(OUT / "method_comparison.csv", comp_rows, list(comp_rows[0].keys()))
    # Maximos alcanzables de cada componente (ayudan a interpretar por que varios perfiles coinciden).
    comp_max = {name: float(table.comps[:, i].max()) for i, name in enumerate("CPASD")}
    max_cov = int(round(comp_max["C"] * 18))
    n_max_cov = int(np.sum(np.isclose(table.comps[:, 0] * 18, max_cov)))
    write_json(OUT / "exhaustive_info.json", {
        "M": catalog.M, "combinaciones": table.n, "segundos_enumeracion_y_componentes": table.seconds,
        "maximo_por_componente": comp_max, "cobertura_maxima_tipos": max_cov,
        "combinaciones_con_cobertura_maxima": n_max_cov,
        "nota": "Los componentes de las C(M,4) combinaciones se calculan una vez con fitness.components; cada perfil solo pondera.",
        "M_conservador": len(cons_ids), "combinaciones_conservador": cons_table.n,
    })
    print("Listo: results/baselines/, ga_vs_optimum.csv, quality_assessment.csv, cross_profile_matrix.csv")


if __name__ == "__main__":
    t0 = time.perf_counter()
    main()
    print(f"Tiempo total: {time.perf_counter() - t0:.1f} s")
