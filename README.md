# TP2 — Optimización del moveset ofensivo de Charizard mediante Algoritmo Genético

**Inteligencia Artificial — UTN FRBA — Grupo 6 — Entrega final (2.º cuatrimestre 2026)**

Repositorio: https://github.com/PabloV2003/tp2-charizard-ga · Informe: [`docs/informe_final.pdf`](docs/informe_final.pdf)

Algoritmo Genético (Python + DEAP) que elige los **cuatro movimientos ofensivos** de Charizard (Fuego/Volador) en
**Pokémon Escarlata/Púrpura**, maximizando

```
F(x) = 100 × (wC·C + wP·P + wA·A + wS·S + wD·D)
```

donde C es la cobertura de tipos, P la potencia media normalizada, A la precisión media, S la proporción de
movimientos con STAB y D la diversidad de tipos. Incluye datos versionados, 80 corridas reales, comparación con
búsqueda aleatoria, heurística voraz y enumeración exhaustiva, pruebas, notebook e informe final (DOCX y PDF).

**Entregables principales**

| Archivo | Contenido |
|---|---|
| `docs/informe_final.docx` / `docs/informe_final.pdf` | Informe final sobre la plantilla oficial de la cátedra |
| `results/runs/R1..R5/seed_42_log.csv` | Logs CSV de las cinco corridas principales (exigidos por la consigna) |
| `notebooks/tp2_charizard.ipynb` | Demostración didáctica ejecutada |
| `docs/guia_defensa.md` | Guía para defender el trabajo |
| `docs/matriz_cumplimiento.md`, `docs/registro_validacion.md` | Matriz de cumplimiento y registro de validación |
| `dist/TP2_Grupo6_Charizard_entrega_final.zip` | Paquete completo (se genera con `scripts/make_package.py`) |

## Instalación

Requisitos: Python 3.11 o superior (verificado con **Python 3.13.14 en Windows 11**). Microsoft Word solo hace
falta para exportar el informe a PDF; Node.js solo para la verificación opcional de legalidad con Showdown.

Windows (PowerShell o cmd), desde la carpeta `entrega_final`:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Linux / macOS (mismos pasos con otra ruta del intérprete; **no verificado en esos sistemas**):

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

En Linux/macOS `pywin32` no se instala (es solo para Windows); el informe se genera con `--no-pdf`.

## Demostración: una corrida

```
.venv\Scripts\python scripts\run_ga.py --config R1 --seed 42
```

Muestra el progreso, el mejor moveset con sus componentes y guarda `results/demo/R1/seed_42_log.csv`
(no pisa los resultados del lote). Otras opciones: `--config R3`, `--seed 45`, `--generations 50`,
`--selection roulette`, `--crossover one_point`, `--mutation-prob 0.2`.

## Reproducir todo

```
.venv\Scripts\python scripts\run_all.py
```

Ejecuta, en orden: 80 corridas (`run_experiments.py`), comparación con otros métodos (`run_baselines.py`),
gráficos desde los CSV (`make_figures.py`), verificación de legalidad (opcional, si hay Node.js), notebook
(`build_notebook.py`), validación (`run_validation.py`), informe (`build_report.py`) y ZIP (`make_package.py`).
Tarda alrededor de 1–2 minutos. Sin Word: `scripts\run_all.py --no-pdf`.

Pasos sueltos:

```
.venv\Scripts\python scripts\run_experiments.py          # 8 configuraciones x 10 semillas
.venv\Scripts\python scripts\run_baselines.py            # exhaustiva, aleatoria, voraz, búsqueda local
.venv\Scripts\python scripts\make_figures.py             # figures/ a partir de results/
.venv\Scripts\python -m pytest -q                        # pruebas
.venv\Scripts\python scripts\build_notebook.py           # regenera y ejecuta el notebook
.venv\Scripts\python scripts\build_report.py             # docs/informe_final.docx + .pdf
.venv\Scripts\python scripts\build_report.py --repo-url https://github.com/USUARIO/REPO   # completa la URL
```

### Datos

El proyecto funciona **sin conexión**: el dataset definitivo ya está en `data/`. Para reconstruirlo desde las
fuentes fijadas por commit (PokéAPI `api-data` y Pokémon Showdown, ver `config/data_sources.json`):

```
.venv\Scripts\python scripts\prepare_data.py --refresh
```

### Verificación opcional de legalidad (Node.js)

```
.venv\Scripts\python scripts\validate_legality_showdown.py --setup
```

Descarga Pokémon Showdown en el commit fijado (en `.cache/`, excluida del paquete) y valida que los cuatro
movimientos de cada moveset resultante puedan coexistir en `[Gen 9] Anything Goes`.

## Estructura

```
config/      experiments.json (pesos R1–R5, parámetros, semillas), quality_criterion.json, data_sources.json, report.json
data/        catalog_moves.csv (M = 53), type_chart.csv (filas = atacante, columnas = defensor), learnset completo,
             verificación cruzada, metadata.json y FUENTES_DATOS.md
src/charizard_ga/   data.py, fitness.py, operators.py, ga.py, baselines.py, experiments.py, config.py, io_utils.py
scripts/     preparación de datos, corridas, comparaciones, gráficos, notebook, validación, informe y paquete
notebooks/   tp2_charizard.ipynb (ejecutado)
results/     runs/<config>/seed_<s>_log.csv y _summary.json, resúmenes, comparaciones, legalidad y validación
figures/     gráficos de las 80 corridas (figures/runs/) y de los análisis
tests/       pruebas (pytest)
docs/        informe final, plantilla oficial, matriz de cumplimiento, registro de validación y guía de defensa
```

## Resultados (resumen)

- Catálogo: 75 movimientos aprendibles en Escarlata/Púrpura → **M = 53** de daño directo → **C(53,4) = 292.825**.
- Las **80 corridas** (5 perfiles de pesos + 3 variantes de operadores, semillas 42–51) alcanzaron el **óptimo
  demostrado** por enumeración exhaustiva de su perfil.
- Perfil base (R1): **Vuelo, Rayo Solar, Terremoto, Puño Certero**, F = 72,7847, 13 de 18 tipos cubiertos
  (la cobertura máxima posible).
- La búsqueda aleatoria con el mismo presupuesto no alcanzó el óptimo en ninguna ejecución; la enumeración exhaustiva
  tarda ~1,4 s y es la referencia exacta. Ver la Discusión del informe sobre las limitaciones del modelo.

## Uso de asistentes de IA

ChatGPT se usó para preparar el prompt de trabajo y Claude Code (Anthropic, Claude Opus 5.5) para el desarrollo
asistido (código, experimentos, gráficos y borrador del informe). Ver la sección 2.10 del informe.
