"""Carga y validacion del dataset local (catalogo de movimientos y tabla de efectividad).

El proyecto funciona sin conexion: todo se lee de la carpeta data/, generada una unica vez por
scripts/prepare_data.py a partir de commits fijos de PokeAPI y Pokemon Showdown.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .paths import DATA_DIR

# Los 18 tipos individuales en el orden canonico de la tabla de tipos.
TYPE_ORDER = (
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
    "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
)
# Tipos de Charizard: los movimientos de estos tipos reciben STAB.
CHARIZARD_TYPES = ("fire", "flying")


@dataclass(frozen=True)
class Move:
    """Un movimiento del catalogo definitivo (atributos vigentes en Escarlata/Purpura)."""

    move_id: int
    slug: str
    nombre_es: str
    nombre_en: str
    tipo: str
    tipo_es: str
    potencia: int
    precision: int
    categoria: str
    stab: bool
    subconjunto_conservador: bool
    efectos_ignorados: str


@dataclass(frozen=True)
class Catalog:
    """Catalogo de movimientos permitidos + tabla de tipos + constantes de normalizacion."""

    moves: dict            # move_id -> Move
    ids: tuple             # IDs ordenados (orden estable para muestreos reproducibles)
    chart: dict            # chart[atacante][defensor] -> multiplicador
    type_es: dict          # tipo -> nombre en espanol
    se_types: dict         # tipo atacante -> frozenset de tipos defensores con multiplicador > 1
    power_max: int         # potencia maxima del catalogo COMPLETO (fija para todas las corridas)
    dataset_version: str   # hash corto del catalogo + tabla de tipos

    @property
    def M(self) -> int:
        return len(self.ids)

    def names(self, moveset, lang: str = "es") -> list[str]:
        attr = "nombre_es" if lang == "es" else "slug"
        return [getattr(self.moves[m], attr) for m in moveset]

    def by_slug(self, slug: str) -> int:
        for m in self.moves.values():
            if m.slug == slug:
                return m.move_id
        raise KeyError(slug)


def _normalized_bytes(path: Path) -> bytes:
    # Se normalizan los finales de linea para que el hash no cambie si git convierte LF/CRLF.
    return path.read_bytes().replace(b"\r\n", b"\n")


def dataset_hash(data_dir: Path = DATA_DIR) -> str:
    content = _normalized_bytes(data_dir / "catalog_moves.csv") + _normalized_bytes(data_dir / "type_chart.csv")
    return hashlib.sha256(content).hexdigest()


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in ("true", "1", "si", "yes")


def load_type_chart(data_dir: Path = DATA_DIR) -> dict:
    """Lee la tabla 18x18. Orientacion explicita: filas = tipo ATACANTE, columnas = tipo DEFENSOR."""
    with (data_dir / "type_chart.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header[0] != "atacante\\defensor" or tuple(header[1:]) != TYPE_ORDER:
            raise ValueError("type_chart.csv no tiene el encabezado esperado (filas=atacante, columnas=defensor)")
        chart = {}
        for row in reader:
            attacker = row[0]
            chart[attacker] = {d: float(v) for d, v in zip(TYPE_ORDER, row[1:])}
    if tuple(chart) != TYPE_ORDER:
        raise ValueError("type_chart.csv debe tener exactamente los 18 tipos como filas")
    for a in TYPE_ORDER:
        for d in TYPE_ORDER:
            if chart[a][d] not in (0.0, 0.5, 1.0, 2.0):
                raise ValueError(f"Multiplicador invalido {a}->{d}: {chart[a][d]}")
    return chart


def load_catalog(data_dir: Path = DATA_DIR) -> Catalog:
    """Carga el catalogo definitivo y valida IDs, tipos y rangos numericos."""
    data_dir = Path(data_dir)
    chart = load_type_chart(data_dir)
    with (data_dir / "types.csv").open(encoding="utf-8", newline="") as fh:
        type_es = {r["tipo"]: r["tipo_es"] for r in csv.DictReader(fh)}

    moves = {}
    with (data_dir / "catalog_moves.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            mv = Move(
                move_id=int(r["move_id"]), slug=r["slug"], nombre_es=r["nombre_es"], nombre_en=r["nombre_en"],
                tipo=r["tipo"], tipo_es=r["tipo_es"], potencia=int(r["potencia"]), precision=int(r["precision"]),
                categoria=r["categoria"], stab=_as_bool(r["stab"]),
                subconjunto_conservador=_as_bool(r["subconjunto_conservador"]),
                efectos_ignorados=r.get("efectos_ignorados", "") or "",
            )
            if mv.move_id in moves:
                raise ValueError(f"ID duplicado en el catalogo: {mv.move_id}")
            if mv.tipo not in TYPE_ORDER:
                raise ValueError(f"Tipo no reconocido en {mv.slug}: {mv.tipo}")
            if mv.potencia <= 0 or not (0 < mv.precision <= 100):
                raise ValueError(f"Valores numericos incoherentes en {mv.slug}")
            if mv.stab != (mv.tipo in CHARIZARD_TYPES):
                raise ValueError(f"Columna STAB incoherente en {mv.slug}")
            moves[mv.move_id] = mv
    if len({m.slug for m in moves.values()}) != len(moves):
        raise ValueError("Nombres de movimientos duplicados")
    if len(moves) < 4:
        raise ValueError("El catalogo necesita al menos cuatro movimientos validos")

    # Para cada tipo atacante: tipos defensores frente a los cuales es superefectivo (multiplicador > 1).
    se_types = {a: frozenset(d for d in TYPE_ORDER if chart[a][d] > 1.0) for a in TYPE_ORDER}
    return Catalog(
        moves=moves,
        ids=tuple(sorted(moves)),
        chart=chart,
        type_es=type_es,
        se_types=se_types,
        power_max=max(m.potencia for m in moves.values()),
        dataset_version=dataset_hash(data_dir)[:12],
    )


def load_metadata(data_dir: Path = DATA_DIR) -> dict:
    return json.loads((Path(data_dir) / "metadata.json").read_text(encoding="utf-8"))
