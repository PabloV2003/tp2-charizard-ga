"""Potencia efectiva de un movimiento: la P de la version F2 de la funcion de aptitud.

F1 (prototipo de la entrega parcial) usa la potencia base que figura en el juego. Eso sobrevalora
movimientos que en combate rinden mucho menos: los que tardan dos turnos, los que pueden fallar por
una condicion ajena a la precision y los fisicos en un Pokemon especial (o al reves).
F2 usa la potencia EFECTIVA, lo que el movimiento pega de verdad por turno con este Pokemon:

    potencia_efectiva = potencia * f_categoria * f_turnos * f_sostenido

  f_categoria  stat ofensivo que usa el movimiento / mejor stat ofensivo del Pokemon (stats base,
               sin EVs ni naturaleza). Charizard (At 84, AtEsp 109): fisicos 84/109 = 0,77; especiales 1.
  f_turnos     carga o recarga: 0,5 (un golpe cada dos turnos: Vuelo, Rayo Solar, Hiperrayo...);
               falla condicional: 0,25 (Punio Certero falla si el usuario recibe dano antes de actuar);
               bloqueo: 0,75 (Enfado obliga a repetirlo 2-3 turnos y luego confunde al usuario);
               retroceso r: 1 - r/2 (Envite Igneo devuelve 33 % del dano causado: 0,835).
  f_sostenido  si el movimiento baja n etapas el propio stat ofensivo que usa, promedio de dos usos
               seguidos: (1 + 2/(2+n)) / 2   (Sofoco, -2 AtEsp: 0,75).

Los factores son supuestos de modelado; estan aca para poder cambiarlos en un solo lugar.
"""
from __future__ import annotations

FACTOR_CARGA_RECARGA = 0.5
FACTOR_FALLA_CONDICIONAL = 0.25
FACTOR_BLOQUEO = 0.75


def factor_categoria(categoria: str, ataque: int, ataque_especial: int) -> float:
    """1 para la categoria del mejor stat ofensivo del Pokemon; para la otra, el cociente entre ambos."""
    usado = ataque if categoria == "physical" else ataque_especial
    return usado / max(ataque, ataque_especial)


def factor_turnos(carga: bool, recarga: bool, falla_condicional: bool, bloqueo: bool, retroceso: float) -> float:
    """Costo por turnos perdidos, fallos condicionales, bloqueo y retroceso (1 = sin costo)."""
    f = 1.0
    if carga or recarga:
        f *= FACTOR_CARGA_RECARGA
    if falla_condicional:
        f *= FACTOR_FALLA_CONDICIONAL
    if bloqueo:
        f *= FACTOR_BLOQUEO
    if retroceso:
        f *= 1 - retroceso / 2
    return f


def factor_sostenido(etapas: int) -> float:
    """Promedio de dos usos seguidos si el movimiento baja `etapas` el propio stat ofensivo."""
    if etapas <= 0:
        return 1.0
    return (1 + 2 / (2 + etapas)) / 2


def potencia_efectiva(potencia: int, categoria: str, ataque: int, ataque_especial: int, carga: bool = False,
                      recarga: bool = False, falla_condicional: bool = False, bloqueo: bool = False,
                      retroceso: float = 0.0, caida_stat_ofensivo: int = 0) -> float:
    return (potencia * factor_categoria(categoria, ataque, ataque_especial)
            * factor_turnos(carga, recarga, falla_condicional, bloqueo, retroceso)
            * factor_sostenido(caida_stat_ofensivo))
