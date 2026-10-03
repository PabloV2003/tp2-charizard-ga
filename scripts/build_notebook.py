"""Genera notebooks/tp2_charizard.ipynb y lo ejecuta de principio a fin en un kernel limpio.

El notebook no contiene una implementacion propia: importa los modulos de src/charizard_ga, de modo que
consola, notebook, experimentos e informe usan exactamente las mismas formulas.

Uso:  python scripts/build_notebook.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
NB_PATH = ROOT / "notebooks" / "tp2_charizard.ipynb"

CELLS = [
    ("md", """# TP2 — Optimización del moveset ofensivo de Charizard con un Algoritmo Genético

**Grupo 6 — Inteligencia Artificial (UTN FRBA), entrega final.**

Este notebook es una demostración didáctica y ejecutable. No reimplementa nada: importa los módulos de
`src/charizard_ga`, que son los mismos que usan la consola (`scripts/run_ga.py`), el lote de experimentos
(`scripts/run_experiments.py`) y el generador del informe. Todos los números se calculan al ejecutar las celdas.

Contenido: 1) datos, 2) tabla de tipos, 3) cromosoma y función de aptitud, 4) operadores genéticos,
5) una corrida completa con DEAP, 6) resultados del lote y comparación con la enumeración exhaustiva."""),
    ("code", """# Configuración: se ubica la carpeta raíz del proyecto (la que contiene config/ y src/) sin rutas absolutas.
import sys
from pathlib import Path

ROOT = Path.cwd()
while not ((ROOT / "config").is_dir() and (ROOT / "src").is_dir()):
    if ROOT.parent == ROOT:
        raise RuntimeError("No se encontró la raíz del proyecto")
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import math
import pandas as pd
import matplotlib.pyplot as plt

from charizard_ga.data import load_catalog, load_metadata, TYPE_ORDER
from charizard_ga.config import load_experiments
from charizard_ga.fitness import components, contributions, fitness, validate_moveset, weighted_fitness, Evaluator
from charizard_ga.ga import run_ga, describe_solution
from charizard_ga.baselines import exhaustive_table, exhaustive_optimum

pd.set_option("display.width", 160)
print("Raíz del proyecto:", ROOT.name)"""),
    ("md", """## 1. Datos

Catálogo definitivo: movimientos que Charizard aprende en **Pokémon Escarlata/Púrpura** (grupo de versiones
`scarlet-violet`, Gen 9), según PokéAPI fijada por commit y verificada contra Pokémon Showdown. Se excluyen
movimientos de estado y los casos que la función aprobada no puede representar (potencia o precisión no
numéricas, golpes múltiples). Ver `data/FUENTES_DATOS.md`."""),
    ("code", """catalog = load_catalog()
meta = load_metadata()
print(f"M = {catalog.M} movimientos; C(M,4) = {math.comb(catalog.M, 4):,} movesets posibles")
print("Potencia máxima del catálogo (normaliza P):", catalog.power_max)
print("Versión del dataset:", catalog.dataset_version, "| excluidos por motivo:", meta["conteos"]["excluidos_por_motivo"])
cat_df = pd.DataFrame([vars(m) for m in catalog.moves.values()])
cat_df[["nombre_es", "tipo_es", "potencia", "precision", "categoria", "stab"]].sort_values(["tipo_es", "potencia"]).head(12)"""),
    ("md", """## 2. Tabla de efectividad

Orientación explícita: **filas = tipo atacante, columnas = tipo defensor**. La cobertura C(x) cuenta los
tipos defensores para los que algún movimiento tiene multiplicador mayor que 1."""),
    ("code", """chart = pd.DataFrame(catalog.chart).T.loc[list(TYPE_ORDER), list(TYPE_ORDER)]
print("Fuego -> Planta:", chart.loc["fire", "grass"], "| Planta -> Fuego:", chart.loc["grass", "fire"])
print("Eléctrico -> Tierra:", chart.loc["electric", "ground"], "| Tierra -> Eléctrico:", chart.loc["ground", "electric"])
chart.loc[["fire", "flying", "ground", "fighting"]]"""),
    ("md", """## 3. Cromosoma y función de aptitud

Un individuo es una lista de **cuatro IDs de movimientos distintos**. El orden no cambia el significado.

F(x) = 100 × (wC·C + wP·P + wA·A + wS·S + wD·D), con componentes en [0, 1]. Perfil base R1:
wC = 0,40; wP = 0,20; wA = 0,15; wS = 0,15; wD = 0,10.

Ejemplo de la entrega parcial: Lanzallamas, Tajo Aéreo, Pulso Dragón, Rayo Solar."""),
    ("code", """exps = load_experiments()
w_base = exps["profiles"]["R1"]
example = [catalog.by_slug(s) for s in ["flamethrower", "air-slash", "dragon-pulse", "solar-beam"]]
comp = components(example, catalog)
print("Movimientos:", catalog.names(example))
print("Tipos cubiertos (", len(comp.covered), "):", [catalog.type_es[t] for t in comp.covered])
print({k: round(v, 6) for k, v in zip("CPASD", comp.as_tuple())})
print("Aportes:", {k: round(v, 4) for k, v in contributions(comp, w_base).items()})
print("F(x) =", round(fitness(example, catalog, w_base), 6))"""),
    ("code", """# Restricciones duras: aptitud 0 para individuos inválidos.
a, b, c, d = example
for label, ms in {"3 movimientos": [a, b, c], "repetido": [a, a, b, c], "fuera del catálogo (Danza Espada)": [a, b, c, 14]}.items():
    print(f"{label:35s} -> válido={validate_moveset(ms, catalog)[0]}, F={fitness(ms, catalog, w_base)}")
# Invariancia frente a permutaciones del mismo moveset.
import itertools
print("Valores distintos entre las 24 permutaciones:", len({fitness(list(p), catalog, w_base) for p in itertools.permutations(example)}))"""),
    ("md", """## 4. Operadores genéticos

- **Inicialización**: 4 movimientos muestreados sin reemplazo.
- **Selección**: torneo de tamaño 3 (`tools.selTournament`) o ruleta (`tools.selRoulette`, con selección uniforme si todas las aptitudes valen 0).
- **Cruza** (por pareja, p = 0,80): uniforme con intercambio por posición p = 0,5 (`tools.cxUniform`) o de un punto (`tools.cxOnePoint`), seguidas de **reparación** de duplicados.
- **Mutación** (por individuo, p = 0,10): reemplaza un gen al azar por un movimiento ausente.
- **Reemplazo** generacional con **elitismo** de 2 individuos.

Demostración de la reparación: dos padres que comparten un movimiento en posiciones distintas."""),
    ("code", """import random
from charizard_ga.ga import ensure_deap_types, INDIVIDUAL_CLASS
from charizard_ga.operators import cx_uniform_repair, mut_replace_one, OperatorCounters
from deap import creator

ensure_deap_types()                      # se puede reejecutar sin advertencias de creator.create
Ind = getattr(creator, INDIVIDUAL_CLASS)
eq, hur, fb, fl, cr = (catalog.by_slug(s) for s in ["earthquake", "hurricane", "focus-blast", "flare-blitz", "crunch"])
from deap import tools
from charizard_ga.operators import repair_duplicates
counters = OperatorCounters()
p1, p2 = Ind([eq, hur, fb, fl]), Ind([cr, eq, a, b])   # Terremoto está en la posición 0 de p1 y en la 1 de p2
print("Padres:", catalog.names(p1), "x", catalog.names(p2))
# Se busca la primera semilla cuya cruza uniforme genera un duplicado, para mostrar la reparación paso a paso.
for seed in range(100):
    random.seed(seed)
    c1, c2 = Ind(p1), Ind(p2)
    tools.cxUniform(c1, c2, 0.5)
    if len(set(c1)) < 4 or len(set(c2)) < 4:
        break
print(f"Semilla {seed}, cruza uniforme SIN reparar:", catalog.names(c1), "|", catalog.names(c2))
pool = list(dict.fromkeys(list(p1) + list(p2)))       # genes disponibles de ambos padres
fixed = [repair_duplicates(child, pool, catalog.ids) for child in (c1, c2)]
print("Después de reparar:", catalog.names(c1), "|", catalog.names(c2), "| posiciones reparadas:", fixed)
print("¿Hijos válidos?", validate_moveset(c1, catalog)[0], validate_moveset(c2, catalog)[0])
m = Ind(p1); mut_replace_one(m, catalog.ids, counters)
print("Mutación:", catalog.names(p1), "->", catalog.names(m))"""),
    ("md", """## 5. Corrida completa con DEAP (R1, semilla 42)

Se ejecuta la corrida principal R1 y se comprueba que reproduce exactamente el log guardado por el lote
(`results/runs/R1/seed_42_log.csv`)."""),
    ("code", """exp_r1 = next(c for c in exps["configs"] if c.config_id == "R1")
print("Parámetros:", exp_r1.ga.to_dict())
res = run_ga(catalog, exp_r1.weights, exp_r1.ga, seed=42, config_id="R1", verbose=True, print_every=40)
saved = pd.read_csv(ROOT / "results" / "runs" / "R1" / "seed_42_log.csv")
new = pd.DataFrame(res.log)
same = new[["aptitud_max", "aptitud_media", "mejor_acumulada"]].equals(saved[["aptitud_max", "aptitud_media", "mejor_acumulada"]])
print("¿Coincide con el log guardado?", same)
sol = describe_solution(res.best_moveset, catalog, exp_r1.weights, w_base)
pd.DataFrame(sol["movimientos"])[["nombre_es", "tipo_es", "potencia", "precision", "categoria", "stab"]]"""),
    ("code", """log = pd.DataFrame(res.log)
fig, ax = plt.subplots(figsize=(7, 3.5))
ax.plot(log.generacion, log.aptitud_media, label="Media", color="#eb6834")
ax.plot(log.generacion, log.aptitud_max, label="Máxima", color="#2a78d6")
ax.step(log.generacion, log.mejor_acumulada, where="post", label="Mejor acumulada", color="#1baf7a", alpha=0.5, linewidth=4)
ax.set_xlabel("Generación"); ax.set_ylabel("Aptitud F"); ax.legend(); ax.set_title("R1, semilla 42")
plt.show()
print(f"Mejor de la corrida: F = {res.best_fitness:.6f} en la generación {res.best_generation}; "
      f"evaluaciones solicitadas {res.evals_requested}, efectivas {res.evals_effective}")"""),
    ("md", """## 6. Resultados del lote y referencia exacta

El lote ejecutó 8 configuraciones × 10 semillas. Como el espacio tiene 292.825 combinaciones, también se
puede **enumerar completo** con la misma función: eso da el óptimo demostrado de cada perfil y permite medir
la brecha del AG. Que la enumeración sea viable es un resultado en sí mismo (ver Discusión del informe)."""),
    ("code", """summary = pd.read_csv(ROOT / "results" / "summary_configs.csv")
quality = pd.read_csv(ROOT / "results" / "quality_assessment.csv")
summary[["config_id", "aptitud_media", "aptitud_desvio", "aptitud_min", "aptitud_max", "generacion_encontrada_media", "moveset_modal"]].merge(
    quality[["config_id", "replicas_alcanzan_optimo"]], on="config_id")"""),
    ("code", """table = exhaustive_table(catalog)
opt = exhaustive_optimum(table, w_base)
print(f"Enumeración de {table.n:,} combinaciones en {table.seconds:.2f} s")
print("Óptimo R1:", round(opt["optimo"], 6), catalog.names(opt["movesets_optimos"][0]), "| empates:", opt["n_empates_optimo"])
print("Brecha del AG (R1, semilla 42):", opt["optimo"] - res.best_fitness)"""),
    ("md", """## Conclusión de la demostración

- El AG encuentra, en esta corrida, la misma combinación que la enumeración exhaustiva; eso **no** demuestra
  que un AG garantice el óptimo: la garantía proviene de la enumeración.
- La aptitud es un indicador simplificado de calidad ofensiva: ignora carga/recarga, fallos condicionales,
  reparto físico/especial, objetos, habilidades y clima. El informe discute estas limitaciones y presenta un
  análisis con un subconjunto conservador del catálogo."""),
]


def build() -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.metadata["language_info"] = {"name": "python"}
    for kind, src in CELLS:
        nb.cells.append(nbformat.v4.new_markdown_cell(src) if kind == "md" else nbformat.v4.new_code_cell(src))
    return nb


def main():
    nb = build()
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": str(NB_PATH.parent)}})
    errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []) if o.get("output_type") == "error"]
    if errors:
        raise SystemExit(f"El notebook produjo {len(errors)} errores")
    NB_PATH.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, NB_PATH)
    print(f"Notebook ejecutado sin errores: {NB_PATH.relative_to(ROOT)} ({sum(c.cell_type == 'code' for c in nb.cells)} celdas de código)")


if __name__ == "__main__":
    sys.exit(main())
