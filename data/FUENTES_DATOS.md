# Registro de fuentes y preparacion de datos

Archivo generado automaticamente por `scripts/prepare_data.py`. No editar a mano.

## Fuentes

- **PokeAPI (fuente principal)**: repositorio https://github.com/PokeAPI/api-data, commit `02a8d9dd1b1a4e102b8b32d786d17017e8c9769a`.
  Volcado estatico de la API REST publica https://pokeapi.co/api/v2/. Fuente comunitaria, no oficial.
- **Pokemon Showdown (verificacion cruzada)**: repositorio https://github.com/smogon/pokemon-showdown, commit `9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e`
  (archivos `data/moves.ts`, `data/learnsets.ts`, `data/typechart.ts`). Fuente comunitaria, no oficial.
- Fecha de obtencion (UTC): 2026-10-03T23:24:57+00:00 a 2026-10-03T23:25:03+00:00.
- Version del dataset (SHA-256 de catalogo + tabla de tipos): `6557b19f60a8`.

## Alcance

- Pokemon: Charizard (tipos Fuego/Volador, PokeAPI id 6).
- Grupo de versiones: `scarlet-violet` (Pokemon Escarlata y Purpura, generation-ix).
- Metodos de aprendizaje incluidos: level-up, machine, egg, tutor. Los movimientos de evento no forman parte del learnset de PokeAPI y se descartan en Showdown (codigo 9S).
- Los atributos (potencia, precision, tipo) se reconstruyen para Escarlata/Purpura con `past_values`, sin mezclar valores de otras versiones.

## Reglas de exclusion (aplicadas en este orden)

- `ESTADO` (17 movimientos): Movimiento de estado: no produce dano directo (fuera del alcance aprobado).
- `POTENCIA_NO_NUMERICA` (3 movimientos): Potencia base no numerica (dano fijo, variable o dependiente del rival/objeto): la funcion aprobada no puede representarla sin inventar un valor.
- `POTENCIA_CERO` (0 movimientos): Potencia 0 informada por la fuente: dato no utilizable como potencia de dano directo.
- `PRECISION_NO_NUMERICA` (2 movimientos): Precision especial no numerica (por ejemplo, 'nunca falla'): no se convierte automaticamente a 100.
- `GOLPES_MULTIPLES` (0 movimientos): Golpes multiples: la potencia por golpe no representa el dano total del movimiento.
- `OHKO` (0 movimientos): Movimiento de KO en un golpe: no tiene potencia base comparable.

Nota: Carga, recarga, fallo condicional, bloqueo, retroceso, autodebuff, prioridad, potencia condicional y tipo variable se conservan en el catalogo como columnas descriptivas, y la columna efectos_ignorados resume en texto lo que la potencia base no refleja. La aptitud F2 usa carga, recarga, fallo condicional, bloqueo, retroceso y la caida del propio stat ofensivo (ademas del reparto fisico/especial de Charizard) para calcular la potencia efectiva (src/charizard_ga/mechanics.py); prioridad, potencia condicional, tipo variable y los demas efectos secundarios no se modelan.

## Resultado

- Learnset total en `scarlet-violet`: 75 movimientos.
- Catalogo definitivo: **M = 53** movimientos; espacio de busqueda **C(M,4) = 292,825** movesets.
- Potencia maxima del catalogo: 150 (normaliza P solo en la aptitud original F1; F2 normaliza con la potencia efectiva maxima del catalogo, registrada en results/parameters.json).
- Subconjunto conservador (solo para sensibilidad, sin carga/recarga/fallo condicional): 46 movimientos.

## Verificacion cruzada con Showdown

- Diferencias en la tabla de tipos 18x18: 0.
- Movimientos del learnset presentes solo en PokeAPI: ninguno.
- Movimientos Gen 9 presentes solo en Showdown: {'falseswipe': ['charmeleon:9M', 'charmander:9M']}.
  Criterio: El catalogo usa el learnset propio de Charizard en PokeAPI. Si un movimiento aparece en Showdown solo por codigos de preevoluciones (charmander/charmeleon), se informa pero no se incorpora.
- Movimientos del catalogo con atributos distintos entre fuentes: ninguno.
- Movimientos del learnset (incluye excluidos) con atributos distintos: ninguno.

## Limite de la comprobacion de legalidad

Se verifica la pertenencia individual de cada movimiento al learnset de Escarlata/Purpura (nivel, MT, huevo, tutor) en dos fuentes independientes. La coexistencia de los cuatro movimientos de un moveset concreto se verifica por separado con el validador de Pokemon Showdown (scripts/validate_legality_showdown.py) para los movimientos resultantes.

## Archivos

- `catalog_moves.csv`: catalogo definitivo usado por el AG (una fila por movimiento).
- `learnset_sv_charizard.csv`: learnset completo con la decision de inclusion y el motivo de exclusion.
- `type_chart.csv`: efectividad 18x18; **filas = tipo atacante, columnas = tipo defensor**.
- `types.csv`: nombres de los tipos en espanol.
- `crosscheck_showdown.csv`: comparacion movimiento por movimiento con Showdown.
- `raw/`: extractos de las respuestas originales (los archivos completos se identifican por SHA-256 en `metadata.json`).
- `metadata.json`: procedencia, filtros, conteos y hashes.

## Movimientos excluidos

| Movimiento | Tipo | Potencia | Precision | Clase | Motivo |
|---|---|---:|---:|---|---|
| Lanzamiento (fling) | dark | None | 100 | physical | POTENCIA_NO_NUMERICA |
| Bramido Dragón (dragon-cheer) | dragon | 0 | 0 | status | ESTADO |
| Danza Dragón (dragon-dance) | dragon | None | None | status | ESTADO |
| Contraataque (counter) | fighting | None | 100 | physical | POTENCIA_NO_NUMERICA |
| Golpe Calor (heat-crash) | fire | None | 100 | physical | POTENCIA_NO_NUMERICA |
| Día Soleado (sunny-day) | fire | None | None | status | ESTADO |
| Fuego Fatuo (will-o-wisp) | fire | None | 85 | status | ESTADO |
| Golpe Aéreo (aerial-ace) | flying | 60 | None | physical | PRECISION_NO_NUMERICA |
| Tambor (belly-drum) | normal | None | None | status | ESTADO |
| Aguante (endure) | normal | None | None | status | ESTADO |
| Gruñido (growl) | normal | None | 100 | status | ESTADO |
| Refuerzo (helping-hand) | normal | None | None | status | ESTADO |
| Protección (protect) | normal | None | None | status | ESTADO |
| Rugido (roar) | normal | None | None | status | ESTADO |
| Cara Susto (scary-face) | normal | None | 100 | status | ESTADO |
| Sonámbulo (sleep-talk) | normal | None | None | status | ESTADO |
| Pantalla de Humo (smokescreen) | normal | None | 100 | status | ESTADO |
| Sustituto (substitute) | normal | None | None | status | ESTADO |
| Meteoros (swift) | normal | 60 | None | special | PRECISION_NO_NUMERICA |
| Danza Espada (swords-dance) | normal | None | None | status | ESTADO |
| Descanso (rest) | psychic | None | None | status | ESTADO |
| Tormenta de Arena (sandstorm) | rock | None | None | status | ESTADO |
