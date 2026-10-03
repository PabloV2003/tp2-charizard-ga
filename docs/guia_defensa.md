# Guía breve para defender el TP2 (Grupo 6)

Todos los números de esta guía salen de `results/` y coinciden con el informe final.

## 1. Flujo del código (de los datos al informe)

1. `scripts/prepare_data.py` descarga (una sola vez, desde commits fijos) el learnset de Charizard en
   Escarlata/Púrpura y los 18 tipos de PokéAPI, los contrasta con Pokémon Showdown y guarda `data/`.
   75 movimientos aprendibles → reglas de exclusión → **catálogo de 53**.
2. `src/charizard_ga/data.py` carga y valida el catálogo y la tabla de tipos (**filas = atacante, columnas = defensor**).
3. `src/charizard_ga/fitness.py` calcula C, P, A, S, D (sin pesos) y luego F = 100 × Σ w·componente.
   Inválido (≠ 4 movimientos, repetidos o fuera del catálogo) → F = 0.
4. `src/charizard_ga/operators.py`: inicialización sin reemplazo, ruleta segura, cruza uniforme / de un punto
   con **reparación de duplicados**, mutación que reemplaza un gen.
5. `src/charizard_ga/ga.py`: ciclo explícito con DEAP (élites → selección → clonación → cruza por pareja →
   mutación por individuo → evaluación → reemplazo → mejor de la corrida) y log por generación.
6. `scripts/run_experiments.py`: 8 configuraciones × 10 semillas = 80 corridas → `results/runs/`.
7. `scripts/run_baselines.py`: exhaustiva, aleatoria, voraz y voraz + búsqueda local con la misma función.
8. `scripts/make_figures.py` → `figures/` (todo desde los CSV); `scripts/build_report.py` → informe DOCX/PDF.

## 2. ¿Por qué un Algoritmo Genético?

- Es un problema de **optimización combinatoria con objetivos en conflicto** (cobertura vs. potencia vs. precisión
  vs. STAB vs. diversidad): no hay una regla simple, el valor de un movimiento depende de los otros tres.
- La solución se codifica directo (4 genes), la calidad se mide con una función (no hay ejemplos etiquetados,
  por eso no una red neuronal) y la cruza combina buenos subconjuntos de movimientos.
- **Honestidad sobre el tamaño:** C(53,4) = 292.825. La enumeración exhaustiva **sí es viable** (≈1,4 s) y la
  usamos como **referencia exacta**. No decimos que el problema sea imposible para un software tradicional; el AG
  se justifica como método de búsqueda pedido por la asignatura y escalable a variantes más grandes
  (por ejemplo, optimizar los movimientos de un equipo completo).

## 3. ¿Qué significan los pesos?

Expresan **qué valora el jugador**. Son entradas del experimento, no constantes oficiales ni óptimos demostrados.

| Perfil | wC | wP | wA | wS | wD | Idea |
|---|---:|---:|---:|---:|---:|---|
| R1 Base | 0,40 | 0,20 | 0,15 | 0,15 | 0,10 | prioriza cobertura general |
| R2 Cobertura | 0,60 | 0,15 | 0,10 | 0,05 | 0,10 | responder a más tipos |
| R3 Potencia | 0,20 | 0,45 | 0,15 | 0,10 | 0,10 | daño bruto |
| R4 Precisión | 0,25 | 0,15 | 0,40 | 0,10 | 0,10 | no fallar |
| R5 STAB+diversidad | 0,25 | 0,15 | 0,10 | 0,30 | 0,20 | aprovechar Fuego/Volador |

P se normaliza con la potencia máxima del **catálogo completo (150)**, fija para todas las corridas. S solo cuenta
cuántos movimientos son Fuego/Volador; no multiplica la potencia (así se aprobó).

## 4. Operadores (y sus probabilidades)

- **Selección por torneo k = 3**: se toman 3 al azar y gana el mejor (por cada padre). **Ruleta**: probabilidad
  proporcional a F; si todas valieran 0, se elige uniforme.
- **Cruza por pareja, p = 0,80**. Uniforme: cada posición se intercambia con p = 0,5. De un punto: se intercambian
  las colas desde un corte.
- **Reparación**: si un hijo queda con un movimiento repetido (p. ej. [Terremoto, Terremoto, Lanzallamas,
  Envite Ígneo]), se conserva la primera aparición y la posición repetida se completa con un movimiento ausente
  tomado al azar de los genes de los padres. El notebook muestra un caso real.
- **Mutación por individuo, p = 0,10**: se reemplaza un gen al azar por un movimiento que el individuo no tiene.
- **Elitismo 2**: los 2 mejores pasan clonados. `selBest` se usa **solo** para esto; los ejemplos docentes lo
  llaman "Ranking", pero no es una selección probabilística por ranking.
- **Paro**: 200 generaciones (+ la generación 0). **Semillas** 42–51; las corridas principales son la 42.
- No usamos `cxOrdered`/`mutShuffleIndexes` del ejemplo del viajero: permutar un moveset no crea una combinación nueva.

## 5. Cómo leer los gráficos

- **Evolución de una corrida** (Fig. 2–6): línea azul = máxima de la generación; aqua ancha = mejor acumulada
  (coinciden por el elitismo); naranja = media con banda ±1 desvío; gris = mínima. Panel inferior: combinaciones
  distintas en la población (diversidad). En R1 la mejor aparece en la generación 7 y la diversidad cae a ~10.
- **Variabilidad** (Fig. 8): cada punto es una semilla; muestra en qué generación y con cuántas evaluaciones
  efectivas se llegó al óptimo.
- **Operadores** (Fig. 9): la ruleta llega más tarde y mantiene más diversidad (media de la población más baja).
- **AG vs. aleatoria** (Fig. 10): con el mismo esfuerzo el AG llega al óptimo; la aleatoria no.
- **Distribución** (Fig. 11): el óptimo es la combinación nº 1 de 292.825; la mayoría ronda F ≈ 50–65.

## 6. Qué permiten concluir los resultados (y qué no)

- **Sí:** bajo el modelo aprobado, las 80 corridas encontraron el **óptimo demostrado** de su perfil (brecha 0);
  el AG fue mucho más eficiente que la búsqueda aleatoria; los pesos cambian la solución (R3 y R5) o no
  (R1 = R2 = R4, porque ese moveset ya tiene la cobertura máxima posible, 13/18, con buena potencia y precisión).
- **No:** no demuestra que un AG garantice el óptimo (la garantía viene de la exhaustiva); no demuestra el mejor
  Charizard competitivo ni una probabilidad de victoria; con 10 semillas no hacemos inferencia estadística sobre
  diferencias de operadores.

## 7. Preguntas probables

**¿Por qué no hicieron búsqueda exhaustiva directamente?** La hicimos, como referencia: tarda ≈1,4 s y confirma el
óptimo. Para este tamaño es el método más directo; lo decimos en la Discusión. El AG es el sistema inteligente pedido
y escala a problemas donde enumerar no es viable.

**¿Cómo saben que es el óptimo?** Enumeramos las 292.825 combinaciones con la misma función y el mismo catálogo.

**¿Por qué aparece Puño Certero (y Vuelo, Rayo Solar, Anillo Ígneo)?** Porque la función usa la potencia base y no
descuenta que Puño Certero falla si Charizard recibe daño, que Vuelo y Rayo Solar cargan un turno o que Anillo
Ígneo/Hiperrayo/Gigaimpacto recargan. Es una limitación del modelo aprobado, documentada. Con el subconjunto
conservador (sin carga, recarga ni fallo condicional) el óptimo base es Terremoto, Envite Ígneo, Onda Certera y Vendaval.

**¿Por qué R1, R2 y R4 dan lo mismo?** La cobertura máxima posible es 13 tipos (300 combinaciones la logran) y entre
ellas ese moveset tiene la mejor potencia/precisión; subir wC no mejora C y subir wA no compensa la potencia perdida.

**¿Por qué en R3 hay dos soluciones?** Hiperrayo y Gigaimpacto tienen el mismo tipo, potencia y precisión: empatan.

**¿La aptitud media siempre sube?** No: en R1 baja en 95 de 200 transiciones (la mutación genera hijos peores);
lo que no baja es la mejor acumulada, por el elitismo.

**¿Por qué reparar y no penalizar?** La penalización dura (F = 0) se mantiene para cualquier inválido, pero reparar
evita desperdiciar hijos y conserva material de los padres. En todas las corridas se registraron 0 inválidos.

**¿Los datos son oficiales?** No: PokéAPI y Showdown son fuentes comunitarias, fijadas por commit y contrastadas entre
sí (tabla de tipos idéntica, 53 movimientos con los mismos atributos). La única diferencia (Falso Tortazo, heredado de
preevoluciones) está documentada.

**¿Los cuatro movimientos pueden estar juntos en un Charizard?** Los 12 movesets resultantes se validaron con el
validador de Showdown ([Gen 9] Anything Goes, regla Obtainable): todos válidos; los controles negativos se rechazan.

**¿Es reproducible?** Sí: semilla por corrida (todo usa `random`, también DEAP), datos fijados, configuración en
JSON; las pruebas y el registro de validación muestran que la misma semilla reproduce el mismo log.

**¿Qué mejorarían?** Potencia efectiva por turno, consistencia física/especial (Charizard: Atq. Esp. 109 vs. Atq. 84),
cobertura contra tipos dobles ponderada por el metajuego, evaluación por simulación, optimización multiobjetivo
(NSGA-II) y extender a equipos completos.

**¿Cómo usaron la IA?** ChatGPT para preparar el prompt de trabajo; Claude Code para el desarrollo asistido (código,
experimentos, gráficos y borrador del informe). Los resultados son ejecuciones reales registradas; la revisión y la
defensa son del grupo. Conviene que cada integrante recorra `src/charizard_ga/ga.py` y el notebook antes de la defensa.
