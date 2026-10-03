# Matriz de cumplimiento

Generada por `scripts/build_report.py` a partir de las evidencias (misma fuente que el Anexo A del informe).

| Requisito de la consigna / del prompt | Sección del informe | Evidencia | Estado |
|---|---|---|---|
| Problema con relevancia; descripción, características y ejemplo | 1.1–1.3 | Informe; entrega parcial | Cumplido |
| No figura en el anexo de problemas resueltos | 1.4 | Consigna, anexo (pág. 25) | Cumplido |
| Justificación del AG (sin afirmar imposibilidad; tamaño real del espacio) | 1.6, 4.3 | C(53,4) medido; exhaustiva | Cumplido |
| Cromosoma y función de aptitud con justificación; versión por corrida | 2.4–2.6 | src/charizard_ga/fitness.py; logs (fitness_version) | Cumplido |
| Métodos de los operadores genéticos usados | 2.7 | src/charizard_ga/operators.py, ga.py | Cumplido |
| Herramientas, lenguaje y librerías | 2.9 | requirements.txt; results/environment.json | Cumplido |
| Asistente de codificación basado en IA | 2.10 | Declaración en el informe | Cumplido |
| Al menos 5 corridas con parámetros distintos | 2.8, 3.1 | 80 corridas en results/runs/ | Cumplido |
| Por corrida: cambios en F/cromosoma, métodos y parámetros | 3.1 | results/parameters.json; summaries | Cumplido |
| Por corrida: gráfico de toda la corrida | 3.1, Anexo D | figures/runs/*.png (desde CSV) | Cumplido |
| Por corrida: mejor solución, interpretación y si resuelve | 3.1 | seed_42_summary.json; ga_vs_optimum.csv | Cumplido |
| Discusión: comparación, ¿resuelve?, otros métodos, mejoras | 3.2–3.6, 4 | results/baselines/ | Cumplido |
| Conclusión: implementación, teoría, problemas, lecciones | 5 | Informe | Cumplido |
| Referencias bibliográficas, datos y fuentes | 6 | data/FUENTES_DATOS.md | Cumplido |
| URL del repositorio con código fuente | 6 | https://github.com/PabloV2003/tp2-charizard-ga | Cumplido |
| Log CSV de las corridas principales en el repositorio | 6 | results/runs/R1..R5/seed_42_log.csv | Cumplido |
| Informe con la plantilla oficial | Todo | docs/plantilla/ (plantilla del Campus) | Cumplido |
| Datos versionados y ejecución sin conexión | 2.1–2.2 | data/; scripts/prepare_data.py | Cumplido |
| Coexistencia de los movimientos | 2.2, 3.7 | results/legality_showdown.csv | Cumplido |
| Pruebas y registro de validación | 3.8 | tests/; docs/registro_validacion.md | Cumplido |
| Notebook ejecutable de principio a fin | — | notebooks/tp2_charizard.ipynb | Cumplido |

Requisitos exclusivos de redes neuronales (3 entrenamientos, métricas de clasificación/estimación, 20 % de prueba, datos en CSV/JPG/WAV): **no corresponden** a este proyecto, que implementa un AG.

Requisitos adicionales del prompt de trabajo verificados:

- Pesos R1–R5 y operadores (ruleta, un punto, mutación 0,20) ejecutados con semillas 42–51: `results/summary_runs.csv`.
- Corridas principales = semilla 42 de R1–R5 (elegida antes de ver resultados): `config/experiments.json`.
- Criterio de calidad definido antes de analizar: `config/quality_criterion.json`.
- Comparación con búsqueda aleatoria, voraz, voraz + búsqueda local y exhaustiva: `results/baselines/`.
- Ejemplo numérico calculado con el mismo código: informe 2.6 y `tests/test_fitness.py`.
- Gráficos generados desde los CSV: `scripts/make_figures.py`.
- Notebook ejecutado: `notebooks/tp2_charizard.ipynb`.
- Guía de defensa: `docs/guia_defensa.md`. Registro de validación: `docs/registro_validacion.md`.
