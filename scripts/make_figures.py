"""Genera todos los graficos A PARTIR DE LOS CSV de results/ y data/ (no recalcula experimentos).

Salidas (figures/):
    runs/<config>_seed<s>.png       evolucion de cada corrida (un grafico por configuracion y semilla)
    fig_tabla_tipos.png             tabla de efectividad 18x18
    fig_variabilidad.png            generacion y evaluaciones hasta el optimo, por configuracion y semilla
    fig_operadores.png              convergencia media: base vs variantes de cruza y de mutacion
    fig_seleccion.png               convergencia media: torneo vs ruleta, ranking y control sobre numero esperado
    fig_componentes_perfiles.png    componentes de las soluciones optimas de cada perfil
    fig_ag_vs_aleatoria.png         mejor acumulada vs evaluaciones efectivas: AG vs busqueda aleatoria
    fig_distribucion_exhaustiva.png distribucion de la aptitud de las C(M,4) combinaciones (perfil base)

Paleta: categorica de referencia validada (modo claro) con el validador de la guia de visualizacion.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator, NullFormatter  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from charizard_ga.config import load_experiments  # noqa: E402
from charizard_ga.data import TYPE_ORDER, load_catalog  # noqa: E402
from charizard_ga.paths import FIGURES_DIR, RESULTS_DIR  # noqa: E402

# Paleta (orden fijo de slots; nunca se cicla) y tinta de la guia de visualizacion.
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
RED, NEUTRAL = "#e34948", "#f0efec"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9.5, "axes.titlesize": 10, "axes.labelsize": 9.5,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "savefig.facecolor": "white", "figure.facecolor": "white", "axes.facecolor": "white",
})
COMMA = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fmt(v: float, nd: int = 3) -> str:
    return f"{v:.{nd}f}".replace(".", ",")


def save(fig, name: str, dpi: int = 200):
    path = FIGURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
def fig_run(cid: str, seed: int, label: str, dpi: int):
    log = read_csv(RESULTS_DIR / "runs" / cid / f"seed_{seed}_log.csv")
    g = np.array([int(r["generacion"]) for r in log])
    mx = np.array([float(r["aptitud_max"]) for r in log])
    mean = np.array([float(r["aptitud_media"]) for r in log])
    sd = np.array([float(r["aptitud_desvio"]) for r in log])
    mn = np.array([float(r["aptitud_min"]) for r in log])
    best = np.array([float(r["mejor_acumulada"]) for r in log])
    distinct = np.array([int(r["combinaciones_distintas"]) for r in log])
    best_gen = int(log[-1]["generacion_mejor_acumulada"])

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(6.2, 4.3), sharex=True, gridspec_kw={"height_ratios": [3, 1.1], "hspace": 0.12})
    ax.fill_between(g, mean - sd, mean + sd, color=S2, alpha=0.15, linewidth=0, label="Media ± 1 desvío")
    ax.plot(g, mn, color=MUTED, linewidth=0.8, alpha=0.8, label="Mínima")
    ax.plot(g, mean, color=S2, linewidth=1.8, label="Media")
    ax.step(g, best, where="post", color=S3, linewidth=4.5, alpha=0.45, label="Mejor acumulada")
    ax.plot(g, mx, color=S1, linewidth=1.6, label="Máxima")
    ax.plot([best_gen], [best[-1]], linestyle="none", marker="o", markersize=7, color=S1, markeredgecolor="white",
            markeredgewidth=1.5, zorder=5, label=f"Mejor de la corrida (gen. {best_gen}; F = {fmt(best[-1])})")
    ax.set_ylabel("Aptitud F")
    ax.yaxis.set_major_formatter(COMMA)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8, ncol=3, handlelength=1.4, columnspacing=1.0)
    ax.set_title(label, loc="left", color=INK, pad=36)
    ax2.plot(g, distinct, color=INK2, linewidth=1.2)
    ax2.set_ylabel("Distintas")
    ax2.set_xlabel("Generación")
    ax2.set_xlim(0, g.max())
    ax2.yaxis.set_major_locator(MaxNLocator(3, integer=True))
    return save(fig, f"runs/{cid}_seed{seed}.png", dpi=dpi)


def fig_type_chart(catalog):
    order = list(TYPE_ORDER)
    m = np.array([[catalog.chart[a][d] for d in order] for a in order])
    code = np.vectorize({0.0: 0, 0.5: 1, 1.0: 2, 2.0: 3}.get)(m)
    cmap = ListedColormap([RED, "#f4b4b3", NEUTRAL, S1])
    fig, ax = plt.subplots(figsize=(6.3, 6.0))
    ax.imshow(code, cmap=cmap, vmin=-0.5, vmax=3.5)
    labels = [catalog.type_es[t] for t in order]
    ax.set_xticks(range(18), labels, rotation=90, fontsize=8)
    ax.set_yticks(range(18), labels, fontsize=8)
    ax.set_xlabel("Tipo DEFENSOR (columnas)")
    ax.set_ylabel("Tipo ATACANTE (filas)")
    ax.xaxis.set_label_position("top")
    ax.xaxis.tick_top()
    ax.grid(False)
    ax.set_xticks(np.arange(-0.5, 18, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 18, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", length=0)
    txt = {0.0: "0", 0.5: "½", 2.0: "2"}
    for i in range(18):
        for j in range(18):
            if m[i, j] != 1.0:
                ax.text(j, i, txt[m[i, j]], ha="center", va="center", fontsize=7.5,
                        color="white" if m[i, j] in (0.0, 2.0) else INK)
    for s in ax.spines.values():
        s.set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (S1, NEUTRAL, "#f4b4b3", RED)]
    ax.legend(handles, ["×2 superefectivo", "×1 neutro", "×½ poco efectivo", "×0 inmune"], loc="upper center",
              bbox_to_anchor=(0.5, -0.02), ncol=4, fontsize=8)
    return save(fig, "fig_tabla_tipos.png")


def fig_variability(exps, gaps):
    cids = [c.config_id for c in exps["configs"]]
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 0.8 + 0.3 * len(cids)), sharey=True)
    for ax, field, xlabel in ((axes[0], "generacion_alcanza_optimo", "Generación en que se alcanza el óptimo"),
                              (axes[1], "efectivas_hasta_optimo", "Evaluaciones efectivas hasta el óptimo")):
        for i, cid in enumerate(cids):
            # Solo las replicas que alcanzaron el optimo de su perfil (y de su version de aptitud).
            vals = [float(g[field]) for g in gaps if g["config_id"] == cid and g[field] != ""]
            if not vals:
                continue
            y = np.full(len(vals), i) + np.linspace(-0.18, 0.18, len(vals))
            ax.scatter(vals, y, s=18, color=S1, alpha=0.75, linewidths=0)
            ax.plot([np.mean(vals)] * 2, [i - 0.3, i + 0.3], color=INK, linewidth=1.6)
        ax.set_xlabel(xlabel)
        ax.grid(axis="y", visible=False)
        if field == "efectivas_hasta_optimo":
            ax.set_xscale("log")
            ax.set_xticks([100, 300, 1000, 3000])
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
            ax.xaxis.set_minor_formatter(NullFormatter())
    axes[0].set_yticks(range(len(cids)), cids)
    axes[0].invert_yaxis()
    axes[0].scatter([], [], s=18, color=S1, label="Réplica que alcanzó el óptimo (semillas 42–51)")
    axes[0].plot([], [], color=INK, linewidth=1.6, label="Media")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return save(fig, "fig_variabilidad.png")


def mean_curves(cid, seeds, field):
    arr = []
    for s in seeds:
        log = read_csv(RESULTS_DIR / "runs" / cid / f"seed_{s}_log.csv")
        arr.append([float(r[field]) for r in log])
    return np.array(arr)


OPERATOR_SERIES = [("R1", "R1: torneo k=3, cruza de conjuntos, mut. 0,10", S1),
                   ("OP-UNIF", "OP-UNIF: cruza binomial aleatoria", S2),
                   ("OP-1P", "OP-1P: cruza simple (un punto)", S3),
                   ("OP-MUTAD", "OP-MUTAD: mutación adaptativa", S4)]
SELECTION_SERIES = [("R1", "R1: torneo k=3", S1), ("OP-RUL", "OP-RUL: ruleta", S2),
                    ("OP-RANK", "OP-RANK: ranking lineal", S3), ("OP-CNE", "OP-CNE: control sobre número esperado", S4)]


def fig_operators(exps, optimum_r1, series=OPERATOR_SERIES, name="fig_operadores.png"):
    """Convergencia media (10 semillas) de la configuracion base frente a variantes de UN operador.

    R1 conserva siempre el primer color; cada figura tiene a lo sumo 4 series (paleta validada de 4).
    """
    seeds = exps["seeds"]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.3))
    for cid, label, color in series:
        best = mean_curves(cid, seeds, "mejor_acumulada")
        mean = mean_curves(cid, seeds, "aptitud_media")
        g = np.arange(best.shape[1])
        axes[0].plot(g, best.mean(axis=0), color=color, linewidth=1.8, label=label)
        axes[1].plot(g, mean.mean(axis=0), color=color, linewidth=1.8, label=label)
    axes[0].axhline(optimum_r1, color=INK2, linewidth=0.9, label="Óptimo exacto (enumeración)", zorder=0)
    axes[0].set_xlim(0, 120)
    axes[0].set_title("Mejor acumulada (media de 10 semillas)", loc="left", fontsize=9)
    axes[1].set_title("Aptitud media de la población (media de 10)", loc="left", fontsize=9)
    for ax in axes:
        ax.set_xlabel("Generación")
        ax.yaxis.set_major_formatter(COMMA)
    axes[0].set_ylabel("Aptitud F (perfil base)")
    axes[1].set_xlim(0, 200)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.13))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return save(fig, name)


def fig_components(catalog, optimum_rows):
    groups = defaultdict(list)
    comps = {}
    for r in optimum_rows:
        key = r["movesets_optimos"].split(" || ")[0]
        groups[key].append(r["perfil"])
        comps[key] = [float(r[c]) for c in "CPASD"]
    colors = [S1, S2, S3]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    n = len(groups)
    width = 0.8 / n
    x = np.arange(5)
    for i, (key, profs) in enumerate(groups.items()):
        names = " + ".join(catalog.moves[catalog.by_slug(s)].nombre_es for s in key.split("|"))
        ax.bar(x + (i - (n - 1) / 2) * width, comps[key], width=width * 0.92, color=colors[i],
               label=f"{'/'.join(profs)}: {names}")
    ax.set_xticks(x, ["C cobertura", "P potencia", "A precisión", "S STAB", "D diversidad"])
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(COMMA)
    ax.set_ylabel("Valor normalizado [0, 1]")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=7.5)
    return save(fig, "fig_componentes_perfiles.png")


def step_mean(curves, grid):
    """Promedia funciones escalonadas (x creciente, mejor acumulada) evaluadas en una grilla comun."""
    vals = []
    for xs, ys in curves:
        idx = np.searchsorted(xs, grid, side="right") - 1
        v = np.where(idx >= 0, ys[np.clip(idx, 0, None)], np.nan)
        vals.append(v)
    return np.nanmean(np.array(vals), axis=0)


def fig_ga_vs_random(exps, optimum_r1):
    ga_curves, rs_curves = [], []
    for s in exps["seeds"]:
        log = read_csv(RESULTS_DIR / "runs" / "R1" / f"seed_{s}_log.csv")
        ga_curves.append((np.array([int(r["evaluaciones_efectivas_acum"]) for r in log]),
                          np.array([float(r["mejor_acumulada"]) for r in log])))
    rs_rows = read_csv(RESULTS_DIR / "baselines" / "random_search_curves_R1.csv")
    for s in exps["seeds"]:
        rows = [r for r in rs_rows if int(r["semilla"]) == s]
        rs_curves.append((np.array([int(r["evaluaciones_efectivas"]) for r in rows]),
                          np.array([float(r["mejor_acumulada"]) for r in rows])))
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    for xs, ys in ga_curves:
        ax.step(xs, ys, where="post", color=S1, alpha=0.18, linewidth=0.9)
    for xs, ys in rs_curves:
        ax.step(xs, ys, where="post", color=S2, alpha=0.18, linewidth=0.9)
    grid = np.unique(np.logspace(2, np.log10(max(c[0].max() for c in rs_curves)), 300).astype(int))
    ga_grid = grid[grid <= min(c[0].max() for c in ga_curves)]
    ax.plot(ga_grid, step_mean(ga_curves, ga_grid), color=S1, linewidth=2.0, label="AG (media de 10 semillas)")
    ax.plot(grid, step_mean(rs_curves, grid), color=S2, linewidth=2.0, label="Búsqueda aleatoria (media de 10 semillas)")
    ax.axhline(optimum_r1, color=INK2, linewidth=0.9)
    ax.text(grid.max(), optimum_r1 + 0.05, "óptimo exacto (enumeración)", ha="right", va="bottom", fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.set_xlim(100, grid.max())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    ax.yaxis.set_major_formatter(COMMA)
    ax.set_xlabel("Evaluaciones efectivas acumuladas (combinaciones distintas evaluadas, escala log.)")
    ax.set_ylabel("Mejor aptitud acumulada (R1)")
    lo = min(min(c[1][np.searchsorted(c[0], 100)] for c in ga_curves), min(c[1][min(np.searchsorted(c[0], 100), len(c[1]) - 1)] for c in rs_curves))
    ax.set_ylim(lo - 0.3, optimum_r1 + 0.6)
    ax.legend(loc="lower right", fontsize=8)
    return save(fig, "fig_ag_vs_aleatoria.png")


def fig_distribution(optimum_r1, gaps):
    hist = [r for r in read_csv(RESULTS_DIR / "baselines" / "exhaustive_histogram.csv") if r["perfil"] == "R1"]
    left = np.array([float(r["desde"]) for r in hist])
    right = np.array([float(r["hasta"]) for r in hist])
    count = np.array([int(r["combinaciones"]) for r in hist])
    greedy = next(r for r in read_csv(RESULTS_DIR / "baselines" / "greedy.csv") if r["perfil"] == "R1" and r["metodo"] == "voraz")
    rs = [float(r["mejor_aptitud"]) for r in read_csv(RESULTS_DIR / "baselines" / "random_search.csv")
          if r["perfil"] == "R1" and r["modo_presupuesto"] == "requested"]
    fig, ax = plt.subplots(figsize=(6.3, 3.2))
    ax.bar(left, count, width=(right - left) * 0.9, align="edge", color=S1, linewidth=0)
    rs_rank = np.mean([float(r["puesto_en_exhaustiva"]) for r in read_csv(RESULTS_DIR / "baselines" / "random_search.csv")
                       if r["perfil"] == "R1" and r["modo_presupuesto"] == "requested"])
    r1_runs = [g for g in gaps if g["config_id"] == "R1"]
    hits = sum(g["alcanza_optimo"] == "True" for g in r1_runs)
    # El voraz va punteado y por encima del optimo: si ambos coinciden, se ven las dos lineas.
    marks = [(optimum_r1, f"Óptimo exacto = AG en {hits}/{len(r1_runs)} semillas (F = {fmt(optimum_r1)}; puesto 1)", INK, 1.6, "-"),
             (float(greedy["mejor_aptitud"]), f"Voraz (F = {fmt(float(greedy['mejor_aptitud']))}; puesto {greedy['puesto_en_exhaustiva']})",
              S2, 1.6, (0, (3, 2))),
             (float(np.mean(rs)), f"Aleatoria, media de {len(rs)} (F = {fmt(float(np.mean(rs)))}; puesto medio {fmt(rs_rank, 1)})",
              MUTED, 1.2, "-")]
    for z, (x, lab, col, lw, ls) in enumerate(marks, start=2):
        ax.axvline(x, color=col, linewidth=lw, linestyle=ls, label=lab, zorder=z)
    ax.legend(loc="upper left", fontsize=7.8, title=f"Referencias (de {count.sum():,} combinaciones)".replace(",", "."),
              title_fontsize=8, alignment="left")
    ax.set_ylim(0, count.max() * 1.42)
    ax.set_xlabel("Aptitud F con el perfil base (R1)")
    ax.set_ylabel("Combinaciones")
    ax.xaxis.set_major_formatter(COMMA)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    ax.grid(axis="x", visible=False)
    return save(fig, "fig_distribucion_exhaustiva.png")


def main():
    catalog = load_catalog()
    exps = load_experiments()
    runs = read_csv(RESULTS_DIR / "summary_runs.csv")
    optimum_rows = read_csv(RESULTS_DIR / "baselines" / "exhaustive_optimum.csv")
    optimum_r1 = float(next(r for r in optimum_rows if r["perfil"] == "R1")["optimo"])
    gaps = read_csv(RESULTS_DIR / "ga_vs_optimum.csv")
    for r in runs:
        main_run = r["corrida_principal"] == "True"
        label = (f"{r['config_id']} · perfil {r['perfil']} ({r['perfil_nombre']}) · semilla {r['semilla']}"
                 f" · aptitud {r['fitness_version']}")
        fig_run(r["config_id"], int(r["semilla"]), label, dpi=200 if main_run else 110)
    out = [fig_type_chart(catalog), fig_variability(exps, gaps), fig_operators(exps, optimum_r1),
           fig_operators(exps, optimum_r1, SELECTION_SERIES, "fig_seleccion.png"),
           fig_components(catalog, optimum_rows), fig_ga_vs_random(exps, optimum_r1), fig_distribution(optimum_r1, gaps)]
    print(f"{len(runs)} graficos de corridas en figures/runs/ y {len(out)} graficos de analisis:")
    for p in out:
        print("  ", p.name)


if __name__ == "__main__":
    main()
