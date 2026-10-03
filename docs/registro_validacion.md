# Registro de validación

Generado por `scripts/run_validation.py` el 2026-10-03T23:36:13+00:00 (UTC). Resultado global: **todas las verificaciones aprobadas**.

Entorno: Python 3.13.14, DEAP 1.4.4, Windows-11-10.0.26200-SP0.

## 1. Pruebas automatizadas (pytest)

- Total 36: 36 aprobadas, 0 fallidas, 0 omitidas. Salida: `36 passed in 0.73s`.
- Casos:

  - `tests.test_baselines::test_exhaustive_on_subset_matches_bruteforce`
  - `tests.test_baselines::test_random_search_is_reproducible_and_valid`
  - `tests.test_baselines::test_greedy_and_local_search`
  - `tests.test_data::test_catalog_size_and_ids`
  - `tests.test_data::test_catalog_values_are_coherent`
  - `tests.test_data::test_dataset_version_matches_metadata`
  - `tests.test_data::test_type_chart_orientation_rows_attacker_columns_defender`
  - `tests.test_data::test_type_chart_known_immunities`
  - `tests.test_data::test_super_effective_sets`
  - `tests.test_fitness::test_example_components_hand_computed`
  - `tests.test_fitness::test_example_fitness_base_profile`
  - `tests.test_fitness::test_invalid_individuals_get_zero`
  - `tests.test_fitness::test_same_type_different_moves_is_valid`
  - `tests.test_fitness::test_permutation_invariance`
  - `tests.test_fitness::test_weights_must_be_valid`
  - `tests.test_fitness::test_components_in_unit_interval`
  - `tests.test_fitness::test_cache_is_isolated_per_weights`
  - `tests.test_fitness::test_partial_components_match_full_at_four`
  - `tests.test_ga::test_population_and_best_invariants[cfg0]`
  - `tests.test_ga::test_population_and_best_invariants[cfg1]`
  - `tests.test_ga::test_population_and_best_invariants[cfg2]`
  - `tests.test_ga::test_population_and_best_invariants[cfg3]`
  - `tests.test_ga::test_same_seed_same_results_excluding_time`
  - `tests.test_ga::test_deap_types_can_be_recreated_without_warnings`
  - `tests.test_ga::test_invalid_config_is_rejected`
  - `tests.test_operators::test_initialization_is_always_valid`
  - `tests.test_operators::test_repair_keeps_unique_genes_and_fills_from_parents`
  - `tests.test_operators::test_crossovers_produce_valid_children_with_parent_genes`
  - `tests.test_operators::test_mutation_changes_exactly_one_gene_to_new_move`
  - `tests.test_operators::test_roulette_handles_zero_total_fitness`
  - `tests.test_results_consistency::test_every_run_has_complete_evidence`
  - `tests.test_results_consistency::test_main_runs_are_seed_42_of_r1_to_r5`
  - `tests.test_results_consistency::test_saved_main_run_is_reproducible`
  - `tests.test_results_consistency::test_ga_never_exceeds_exhaustive_optimum`
  - `tests.test_results_consistency::test_config_summary_matches_runs`
  - `tests.test_results_consistency::test_main_figures_exist`

Cobertura de los requisitos de verificación:

| Verificación pedida | Prueba |
|---|---|
| Fórmulas C/P/A/S/D y F contra un caso calculado independientemente | `test_fitness::test_example_components_hand_computed`, `test_example_fitness_base_profile` |
| Aptitud 0 ante longitud incorrecta, repetidos o IDs no permitidos | `test_fitness::test_invalid_individuals_get_zero` |
| Invariancia frente a permutaciones | `test_fitness::test_permutation_invariance` |
| Orientación y valores de la tabla de tipos, incluidas inmunidades | `test_data::test_type_chart_*`, `test_super_effective_sets` |
| Inicialización, cruza/reparación y mutación coherentes con las restricciones | `test_operators::*` |
| Tamaño constante, élites conservadas, mejor acumulada coherente | `test_ga::test_population_and_best_invariants` |
| Misma semilla y configuración => mismos resultados (sin tiempos) | `test_ga::test_same_seed_same_results_excluding_time`, `test_results_consistency::test_saved_main_run_is_reproducible` |
| Gráficos, tablas y resúmenes coinciden con los logs | `test_results_consistency::*` y controles del informe (`claim`) |
| Reinicialización correcta de DEAP entre corridas | `test_ga::test_deap_types_can_be_recreated_without_warnings` |
| Caché aislada por pesos/dataset | `test_fitness::test_cache_is_isolated_per_weights` |

## 2. Reproducibilidad de las corridas principales (semilla 42)

- R1: log reproducido idéntico = sí
- R2: log reproducido idéntico = sí
- R3: log reproducido idéntico = sí
- R4: log reproducido idéntico = sí
- R5: log reproducido idéntico = sí

## 3. Ejecución desde cero con el dataset local y rutas relativas

Se copiaron `src/`, `scripts/`, `config/` y `data/` (sin la caché de descargas) a una carpeta temporal y se ejecutó `python scripts/run_ga.py --config R1 --seed 42` desde allí.

- Código de salida: 0; log idéntico al guardado: sí; sin caché de descargas: sí.
- Última línea de la salida: `Log: <copia_temporal>\results\demo\R1\seed_42_log.csv`

## 4. Notebook

- `notebooks/tp2_charizard.ipynb`: 10 celdas de código, ejecutadas en orden sí, errores: 0. Se regenera y ejecuta en un kernel nuevo con `scripts/build_notebook.py` (no depende de estado oculto).

## 5. Gráficos

- 80 gráficos de corridas y 6 de análisis; faltantes: ninguno. Todos se generan desde los CSV con `scripts/make_figures.py`.

## 6. Informe

- Figuras numeradas: 14; tablas numeradas: 25; marcadores sin resolver: ninguno; marcadores [COMPLETAR] intencionales: 0 (URL del repositorio ya completada).
- Las afirmaciones cuantitativas y cualitativas del texto se generan desde los archivos de resultados y se verifican con `claim(...)` en `scripts/build_report.py`.
- Revisión visual del PDF (portada, índice, márgenes, tablas, fórmulas, ejes, leyendas, numeración y cortes de página): realizada sobre las páginas renderizadas; ver detalle en la sección 8.

## 7. Legalidad conjunta de los movesets (verificación externa opcional)

- Validador de Pokémon Showdown, formato `gen9anythinggoes` (Standard AG -> Obtainable), commit `9fb3a5b99f1a`: 12/12 movesets resultantes válidos; 2/2 controles negativos rechazados.

## 8. Revisión manual del informe y correcciones aplicadas

Durante la revisión visual de las páginas renderizadas del PDF se detectaron y corrigieron:

- Índice demasiado largo (incluía el nivel 3) y pegado al resumen: ahora va en página propia y con niveles 1–2.
- Subíndices de los encabezados de tabla (w_C, w_P...) mostrados como texto literal: corregido el marcado.
- Nombres de archivos y funciones con acentos graves literales: ahora se muestran en fuente monoespaciada.
- Tablas cortas partidas entre páginas con el título solo al pie: las filas se mantienen juntas.
- Textos sin tildes provenientes de la configuración y de las notas del catálogo: corregidos en origen.
- Motivos de exclusión en mayúsculas (códigos internos) en el Anexo C: reemplazados por descripciones.
- Gráficos: anotaciones superpuestas a curvas, etiquetas fuera del eje y ticks logarítmicos superpuestos: corregidos.

## 9. Errores de desarrollo detectados y corregidos

- Lector de banderas de Showdown: no marcaba Vuelo/Excavar como movimientos con carga (banderas en varias líneas).
- Diferencia de 2e-16 entre el óptimo calculado con numpy y la aptitud del AG: el óptimo se recalcula con la misma rutina.
- La afirmación inicial sobre la heurística voraz (primer movimiento elegido) no coincidía con el log de pasos: se corrigió el texto y se agregó un `claim` que la verifica.

