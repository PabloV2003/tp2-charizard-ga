"""Optimizacion del moveset ofensivo de Charizard mediante un Algoritmo Genetico (TP2, Grupo 6).

Modulos:
    paths      -> rutas del proyecto (relativas a la carpeta raiz).
    data       -> carga y valida el catalogo de movimientos y la tabla de tipos.
    fitness    -> funcion de aptitud: componentes C/P/A/S/D, ponderacion y validacion.
    operators  -> operadores geneticos adaptados al cromosoma de cuatro movimientos.
    ga         -> ciclo evolutivo explicito con DEAP y registro por generacion.
    baselines  -> metodos de comparacion: busqueda aleatoria, voraz, busqueda local y exhaustiva.
    config     -> lectura de las configuraciones de experimentos.
    io_utils   -> escritura de logs y resumenes.
"""

__version__ = "1.0.0"
