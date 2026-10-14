# TP2 — Optimización del moveset ofensivo de Charizard mediante Algoritmo Genético

**Inteligencia Artificial — UTN FRBA — Grupo 6 — Entrega final (2.º cuatrimestre 2026)**

Repositorio: https://github.com/PabloV2003/tp2-charizard-ga

Algoritmo Genético (Python + DEAP) que elige los **cuatro movimientos ofensivos** de Charizard (Fuego/Volador) en
**Pokémon Escarlata/Púrpura**, maximizando

```
F(x) = 100 × (wC·C + wP·P + wA·A + wS·S + wD·D)
```

donde C es la cobertura de tipos, P la potencia efectiva media normalizada, A la precisión media, S la proporción
de movimientos con STAB y D la diversidad de tipos.

- **Aptitud F2.** P usa la *potencia efectiva* de cada movimiento: la potencia base con descuentos por categoría
  (físico o especial, según las estadísticas de Charizard), turno de carga o recarga, fallo condicional, bloqueo,
  retroceso y caída del propio stat ofensivo (`src/charizard_ga/mechanics.py`). La aptitud original F1 (potencia
  base) se conserva solo como referencia, en la configuración ORIG-R1.
- **Cruza de conjuntos** por defecto: los movimientos que comparten los dos padres pasan a ambos hijos y nunca se
  generan repetidos.
- **Métodos de la teoría** como variantes: selección por ruleta, ranking lineal y control sobre número esperado;
  cruza binomial aleatoria y simple; mutación adaptativa; paro por estancamiento.

Incluye datos versionados, 150 corridas reales (15 configuraciones × 10 semillas), comparación con búsqueda
aleatoria, heurística voraz y enumeración exhaustiva, pruebas y un notebook ejecutado. El informe final se escribe
aparte (`informe_tp2_charizard.md`) a partir de los resultados de este repositorio.

**Entregables principales**

| Archivo | Contenido |
|---|---|
| `results/runs/R1..R5/seed_42_log.csv` | Logs CSV de las cinco corridas principales (exigidos por la consigna) |
| `results/summary_runs.csv`, `results/summary_configs.csv` | Resumen de las 150 corridas y de las 15 configuraciones |
| `figures/` | Gráfico de cada corrida (`figures/runs/`) y de los análisis |
| `notebooks/tp2_charizard.ipynb` | Demostración didáctica ejecutada |
| `docs/registro_validacion.md` | Registro de validación: pruebas, reproducibilidad, notebook, gráficos y legalidad |
| `dist/TP2_Grupo6_Charizard_entrega_final.zip` | Paquete completo (se genera con `scripts/make_package.py`) |

## Instalación

Requisitos: Python 3.11 o superior; Node.js solo para la verificación opcional de legalidad con Showdown.
Verificado en Linux: los experimentos se generaron con Python 3.12.3 (`results/environment.json`) y el notebook,
los gráficos y la validación se regeneraron con Python 3.14.7 (`docs/registro_validacion.md`).

Linux / macOS, desde la carpeta del proyecto:

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

En Windows (PowerShell o cmd) los pasos son los mismos con `python` y `.venv\Scripts\python`; esta versión no se
verificó en Windows.

## Demostración: una corrida

```
.venv/bin/python scripts/run_ga.py --config R1 --seed 42
```

Muestra el progreso, el mejor moveset con sus componentes y guarda `results/demo/R1/seed_42_log.csv`
(no pisa los resultados del lote). Otras opciones: `--config R3`, `--seed 45`, `--generations 50`,
`--selection ranking`, `--crossover uniform`, `--mutation-mode adaptive`, `--stop stagnation` y `--fitness F1`
(aptitud original, para comparar).

## Reproducir todo

```
.venv/bin/python scripts/run_all.py
```

Ejecuta, en orden: las 150 corridas (`run_experiments.py`), la comparación con otros métodos (`run_baselines.py`),
los gráficos desde los CSV (`make_figures.py`), la verificación de legalidad (opcional, si hay Node.js), el
notebook (`build_notebook.py`), la validación (`run_validation.py`) y el ZIP (`make_package.py`). Tarda alrededor
de un minuto y medio (sin contar la primera descarga de Showdown). Con las mismas semillas se obtienen los mismos
logs y resultados; solo cambian los tiempos medidos.

Pasos sueltos:

```
.venv/bin/python scripts/run_experiments.py          # 15 configuraciones x 10 semillas
.venv/bin/python scripts/run_baselines.py            # exhaustiva (F2 y F1), aleatoria, voraz, búsqueda local
.venv/bin/python scripts/make_figures.py             # figures/ a partir de results/
.venv/bin/python -m pytest -q                        # pruebas
.venv/bin/python scripts/build_notebook.py           # regenera y ejecuta el notebook
.venv/bin/python scripts/run_validation.py           # docs/registro_validacion.md
```

### Datos

El proyecto funciona **sin conexión**: el dataset definitivo ya está en `data/`. Para reconstruirlo desde las
fuentes fijadas por commit (PokéAPI `api-data` y Pokémon Showdown, ver `config/data_sources.json`):

```
.venv/bin/python scripts/prepare_data.py --refresh
```

### Verificación opcional de legalidad (Node.js)

```
.venv/bin/python scripts/validate_legality_showdown.py --setup
```

Descarga Pokémon Showdown en el commit fijado (en `.cache/`, excluida del paquete) y valida que los cuatro
movimientos de cada moveset resultante puedan coexistir en `[Gen 9] Anything Goes`. El resultado queda en
`results/legality_showdown.csv`.

## Estructura

```
config/      experiments.json (perfiles R1–R5, parámetros, semillas y las 15 configuraciones),
             quality_criterion.json, data_sources.json
data/        catalog_moves.csv (M = 53), type_chart.csv (filas = atacante, columnas = defensor), learnset completo,
             verificación cruzada, extractos crudos (raw/), metadata.json y FUENTES_DATOS.md
src/charizard_ga/   data.py, mechanics.py, fitness.py, operators.py, ga.py, baselines.py, experiments.py,
                    config.py, io_utils.py, paths.py
scripts/     preparación de datos, corridas, comparaciones, gráficos, legalidad, notebook, validación y paquete
notebooks/   tp2_charizard.ipynb (ejecutado)
results/     runs/<config>/seed_<s>_log.csv y _summary.json, resúmenes, comparaciones (baselines/), legalidad y validación
figures/     gráficos de las 150 corridas (figures/runs/) y de los análisis
tests/       pruebas (pytest)
docs/        registro de validación
```

## Resultados (resumen)

- Catálogo: 75 movimientos aprendibles en Escarlata/Púrpura → **M = 53** de daño directo → **C(53,4) = 292.825**
  combinaciones. La enumeración exhaustiva tarda ~1,1 s y da el óptimo exacto de cada perfil.
- Óptimos con F2: **Terremoto, Llamarada, Onda Certera, Vendaval** para R1, R3 y R5 (R1: F = 71,5096, 11 de 18
  tipos cubiertos); **Terremoto, Triturar, Onda Certera, Vendaval** para R2 (13 tipos, la cobertura máxima
  posible) y **Lanzallamas, Terremoto, Triturar, Tajo Aéreo** para R4.
- **143 de las 150 corridas** alcanzaron el óptimo demostrado de su perfil: todas las configuraciones lo logran en
  las 10 semillas, salvo OP-POB20 (población 20 y 30 generaciones), que lo alcanza en 3 de 10.
- ORIG-R1 (aptitud F1 y cruza binomial aleatoria) encuentra el óptimo de la versión original: **Vuelo, Rayo Solar,
  Terremoto, Puño Certero** (F1 = 72,7847). Medido con F2, ese moveset vale 65,81 y queda en el puesto 4.174 de
  292.825, porque se apoya en movimientos con turno de carga (Vuelo, Rayo Solar) o fallo condicional (Puño Certero).
- Con el mismo número de evaluaciones efectivas que el AG, la búsqueda aleatoria no alcanzó el óptimo en ninguna de
  las 50 ejecuciones (5 perfiles × 10 semillas). La heurística voraz también lo alcanza en los cinco perfiles, con
  206 evaluaciones; la enumeración exhaustiva es la referencia exacta.
- Los 12 movesets validados con el validador de Pokémon Showdown (todos los resultados del AG y de los otros
  métodos, más el ejemplo de la entrega parcial) son legales, y los 2 controles negativos se rechazan.

## Uso de asistentes de IA

ChatGPT se usó para preparar el prompt de trabajo y Claude Code (Anthropic, Claude Opus 5.5) para el desarrollo
asistido (código, experimentos, gráficos y documentación).
