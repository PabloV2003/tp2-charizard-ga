"""Prepara el dataset definitivo del TP2 (catalogo de movimientos de Charizard y tabla de tipos).

Que hace este script (en orden):
  1. Descarga, desde commits FIJOS de PokeAPI (api-data) y Pokemon Showdown, los archivos
     necesarios. Las descargas se guardan en data/cache/ para no repetirlas.
  2. Extrae el learnset de Charizard en el grupo de versiones "scarlet-violet" (Gen 9).
  3. Reconstruye los atributos de cada movimiento VIGENTES en Escarlata/Purpura usando
     "past_values" (para no mezclar atributos de otra version).
  4. Construye la tabla de efectividad 18x18 (filas = tipo atacante, columnas = tipo defensor).
  5. Aplica las reglas de inclusion/exclusion documentadas y valida el resultado.
  6. Verifica contra Showdown (fuente independiente) learnset, potencia, precision, tipo,
     categoria y tabla de tipos, y extrae banderas mecanicas descriptivas.
  7. Escribe data/*.csv, data/metadata.json, data/raw/*.json (extractos) y data/FUENTES_DATOS.md.

Uso:
    python scripts/prepare_data.py            # usa data/cache si existe; si no, descarga
    python scripts/prepare_data.py --refresh  # fuerza la descarga desde los commits fijados

El resto del proyecto (AG, experimentos, informe) solo lee los archivos de data/, por lo que
funciona sin conexion una vez preparado el dataset.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import platform
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "data_sources.json"
DATA = ROOT / "data"
CACHE = DATA / "cache"
RAW = DATA / "raw"

# Orden canonico de los 18 tipos (el mismo que usan los juegos en la tabla de tipos).
TYPE_ORDER = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
    "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
]

# Codigos de exclusion: cada movimiento del learnset se clasifica con UNA regla, en este orden.
EXCLUSION_RULES = {
    "ESTADO": "Movimiento de estado: no produce dano directo (fuera del alcance aprobado).",
    "POTENCIA_NO_NUMERICA": "Potencia base no numerica (dano fijo, variable o dependiente del rival/objeto): la funcion aprobada no puede representarla sin inventar un valor.",
    "POTENCIA_CERO": "Potencia 0 informada por la fuente: dato no utilizable como potencia de dano directo.",
    "PRECISION_NO_NUMERICA": "Precision especial no numerica (por ejemplo, 'nunca falla'): no se convierte automaticamente a 100.",
    "GOLPES_MULTIPLES": "Golpes multiples: la potencia por golpe no representa el dano total del movimiento.",
    "OHKO": "Movimiento de KO en un golpe: no tiene potencia base comparable.",
}


# ---------------------------------------------------------------------------
# Descarga con cache y registro de procedencia
# ---------------------------------------------------------------------------
class Downloader:
    """Descarga archivos y registra URL, hash SHA-256, tamano y fecha de obtencion."""

    def __init__(self, refresh: bool):
        self.refresh = refresh
        CACHE.mkdir(parents=True, exist_ok=True)
        self.manifest_path = CACHE / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8")) if self.manifest_path.exists() else {}
        self.downloaded = 0
        self.from_cache = 0

    def get_bytes(self, url: str, cache_name: str) -> bytes:
        path = CACHE / cache_name
        if path.exists() and not self.refresh and url in self.manifest:
            self.from_cache += 1
            return path.read_bytes()
        self.downloaded += 1
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                data = resp.read()
        except Exception as exc:  # pragma: no cover - depende de la red
            raise SystemExit(
                f"No se pudo descargar {url}: {exc}.\n"
                "Si no hay conexion, no hace falta ejecutar este script: data/ ya contiene el dataset definitivo."
            )
        path.write_bytes(data)
        self.manifest[url] = {
            "archivo_cache": cache_name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "obtenido_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        }
        return data

    def get_json(self, url: str, cache_name: str):
        return json.loads(self.get_bytes(url, cache_name).decode("utf-8"))

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def id_from_url(url: str) -> int:
    return int(url.rstrip("/").split("/")[-1])


def name_in(names: list, lang: str) -> str | None:
    for entry in names:
        if entry["language"]["name"] == lang:
            return entry["name"]
    return None


# ---------------------------------------------------------------------------
# Atributos vigentes en el grupo de versiones objetivo
# ---------------------------------------------------------------------------
def values_for_version_group(move: dict, target_order: int, vg_order: dict[int, int]) -> tuple[dict, list]:
    """Devuelve los atributos del movimiento vigentes en el grupo de versiones objetivo.

    En PokeAPI, cada entrada de "past_values" guarda los valores que el movimiento tenia ANTES
    del grupo de versiones indicado (por ejemplo, Lanzallamas tiene {power: 95, version_group: x-y}
    porque en X/Y bajo de 95 a 90). Los campos en null significan "no cambio en ese punto".
    Para un objetivo T, el valor de cada campo es el de la entrada MAS TEMPRANA posterior a T
    donde el campo no es null; si no hay ninguna, rige el valor actual.
    """
    values = {
        "power": move["power"],
        "accuracy": move["accuracy"],
        "type": move["type"]["name"],
        "pp": move["pp"],
        "effect_chance": move["effect_chance"],
    }
    later = [pv for pv in move["past_values"] if vg_order[id_from_url(pv["version_group"]["url"])] > target_order]
    applied = []
    # Se aplican de la mas tardia a la mas temprana: la mas temprana queda con la ultima palabra.
    for pv in sorted(later, key=lambda p: vg_order[id_from_url(p["version_group"]["url"])], reverse=True):
        for field in ("power", "accuracy", "pp", "effect_chance"):
            if pv.get(field) is not None:
                values[field] = pv[field]
                applied.append(f"{field}<-{pv['version_group']['name']}")
        if pv.get("type") is not None:
            values["type"] = pv["type"]["name"]
            applied.append(f"type<-{pv['version_group']['name']}")
    return values, applied


# ---------------------------------------------------------------------------
# Lectura liviana de los archivos TypeScript de Showdown
# ---------------------------------------------------------------------------
def ts_top_blocks(text: str) -> dict[str, str]:
    """Separa los bloques de primer nivel '\tclave: { ... \t},' de un archivo de datos de Showdown."""
    return {m.group(1): m.group(2) for m in re.finditer(r"^\t(\w+): \{\n(.*?)^\t\},?$", text, flags=re.M | re.S)}


def parse_showdown_move(block: str) -> dict:
    def one(pattern, cast=str):
        m = re.search(pattern, block, flags=re.M)
        return cast(m.group(1)) if m else None

    acc_raw = one(r"^\t\taccuracy: (true|\d+),")
    # Las banderas pueden ocupar una o varias lineas: se captura hasta la llave de cierre.
    flags_match = re.search(r"^\t\tflags: \{(.*?)\},", block, flags=re.M | re.S)
    flags_raw = flags_match.group(1) if flags_match else ""
    flags = {k.strip() for k, _ in (f.split(":") for f in flags_raw.split(",") if ":" in f)}
    if "twoturnmove" in block:  # movimientos de dos turnos (Vuelo, Excavar, Rayo Solar...)
        flags.add("charge")
    recoil = re.search(r"^\t\trecoil: \[(\d+), (\d+)\]", block, flags=re.M)
    self_boosts = re.search(r"self: \{\s*boosts: \{([^}]*)\}", block, flags=re.S)
    drops = {}
    if self_boosts:
        for k, v in re.findall(r"(\w+): (-?\d+)", self_boosts.group(1)):
            if int(v) < 0:
                drops[k] = int(v)
    callbacks = sorted(set(re.findall(r"^\t\t(\w+)\(", block, flags=re.M)))
    return {
        "num": one(r"^\t\tnum: (-?\d+),", int),
        "name": one(r'^\t\tname: "(.*?)",'),
        "basePower": one(r"^\t\tbasePower: (\d+),", int),
        "accuracy": None if acc_raw is None else (True if acc_raw == "true" else int(acc_raw)),
        "category": one(r'^\t\tcategory: "(\w+)",'),
        "type": one(r'^\t\ttype: "(\w+)",'),
        "priority": one(r"^\t\tpriority: (-?\d+),", int) or 0,
        "isNonstandard": one(r'^\t\tisNonstandard: "(\w+)",'),
        "multihit": one(r"^\t\tmultihit: (.+),"),
        "ohko": bool(re.search(r"^\t\tohko: ", block, flags=re.M)),
        "flags": sorted(flags),
        "recoil": [int(recoil.group(1)), int(recoil.group(2))] if recoil else None,
        "self_drops": drops,
        "mustrecharge": "mustrecharge" in block,
        "lockedmove": "lockedmove" in block,
        "forceSwitch": bool(re.search(r"^\t\tforceSwitch: true", block, flags=re.M)),
        "partiallytrapped": "partiallytrapped" in block,
        "callbacks": callbacks,
    }


def showdown_learnset_gen9(blocks: dict[str, str], species: list[str]) -> dict[str, list[str]]:
    """Movimientos aprendibles en Gen 9 (codigos '9L', '9M', '9E', '9T'); se excluyen eventos '9S'."""
    result: dict[str, list[str]] = {}
    for sp in species:
        block = blocks.get(sp, "")
        for move_id, codes in re.findall(r"^\t\t\t(\w+): \[(.*?)\],", block, flags=re.M):
            gen9 = [c.strip().strip('"') for c in codes.split(",") if c.strip().strip('"').startswith("9")]
            gen9 = [c for c in gen9 if not c.startswith("9S")]
            if gen9:
                result.setdefault(move_id, []).extend(f"{sp}:{c}" for c in gen9)
    return result


def showdown_typechart(text: str) -> dict[str, dict[str, float]]:
    """Devuelve mult[atacante][defensor] a partir de damageTaken (codificado por tipo defensor)."""
    code_to_mult = {0: 1.0, 1: 2.0, 2: 0.5, 3: 0.0}
    chart: dict[str, dict[str, float]] = {}
    for defender, block in ts_top_blocks(text).items():
        if defender not in TYPE_ORDER:
            continue
        for attacker, code in re.findall(r"^\t\t\t(\w+): (\d),", block, flags=re.M):
            att = attacker.lower()
            if att in TYPE_ORDER:
                chart.setdefault(att, {})[defender] = code_to_mult[int(code)]
    return chart


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def mechanic_notes(sd: dict) -> dict:
    """Traduce las banderas de Showdown a columnas descriptivas en espanol.

    Estas columnas NO modifican la aptitud: solo documentan que efectos ignora el modelo aprobado.
    """
    cb = set(sd["callbacks"])
    notes = []
    charge = "charge" in sd["flags"]
    recharge = "recharge" in sd["flags"] or sd["mustrecharge"]
    fails = bool({"beforeMoveCallback", "priorityChargeCallback"} & cb)
    cond_power = bool({"basePowerCallback", "onBasePower"} & cb)
    var_type = bool({"onModifyType"} & cb)
    if charge:
        notes.append("requiere turno de carga")
    if recharge:
        notes.append("obliga a recargar un turno")
    if sd["recoil"]:
        notes.append(f"retroceso {sd['recoil'][0]}/{sd['recoil'][1]} del daño causado")
    if sd["self_drops"]:
        notes.append("baja estadísticas propias " + ", ".join(f"{k} {v}" for k, v in sd["self_drops"].items()))
    if sd["lockedmove"]:
        notes.append("bloquea 2-3 turnos y luego confunde al usuario")
    if fails:
        notes.append("falla si el usuario recibe daño antes de actuar")
    if cond_power:
        notes.append("potencia condicional (el modelo usa la potencia base)")
    if var_type:
        notes.append("tipo variable según clima/teracristalización (el modelo usa el tipo base)")
    if sd["forceSwitch"]:
        notes.append("fuerza el cambio del rival")
    if sd["partiallytrapped"]:
        notes.append("atrapa al rival varios turnos")
    if sd["priority"]:
        notes.append(f"prioridad {sd['priority']:+d}")
    return {
        "carga": charge,
        "recarga": recharge,
        "retroceso": bool(sd["recoil"]),
        "autodebuff": bool(sd["self_drops"]),
        "bloqueo": sd["lockedmove"],
        "falla_condicional": fails,
        "potencia_condicional": cond_power,
        "tipo_variable": var_type,
        "prioridad": sd["priority"],
        "efectos_ignorados": "; ".join(notes),
        # Subconjunto conservador (solo para analisis de sensibilidad, no es el catalogo principal):
        # excluye movimientos que necesitan un turno extra o que pueden fallar por una condicion
        # ajena a la precision, porque su potencia base sobreestima el dano por turno.
        "subconjunto_conservador": not (charge or recharge or fails),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="vuelve a descargar desde los commits fijados")
    args = parser.parse_args()
    t_start = time.perf_counter()

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    RAW.mkdir(parents=True, exist_ok=True)
    dl = Downloader(args.refresh)
    pk = cfg["pokeapi"]
    pk_base = pk["url_base"].format(commit=pk["commit"])
    sd_cfg = cfg["showdown"]
    sd_base = sd_cfg["url_base"].format(commit=sd_cfg["commit"])
    target_vg = cfg["version_group"]

    def pk_get(path: str):
        return dl.get_json(f"{pk_base}/{path}/index.json", "pokeapi_" + path.replace("/", "_") + ".json")

    # 1) Learnset de Charizard en el grupo de versiones objetivo -------------------------------
    pokemon = pk_get(f"pokemon/{cfg['pokemon']['pokeapi_id']}")
    assert pokemon["name"] == cfg["pokemon"]["nombre"], "El id no corresponde a Charizard"
    poke_types = [t["type"]["name"] for t in sorted(pokemon["types"], key=lambda t: t["slot"])]
    base_stats = {s["stat"]["name"]: s["base_stat"] for s in pokemon["stats"]}
    assert poke_types == cfg["pokemon"]["tipos"], f"Tipos inesperados: {poke_types}"

    learnset = []
    for entry in pokemon["moves"]:
        details = [d for d in entry["version_group_details"] if d["version_group"]["name"] == target_vg]
        methods = sorted({(d["move_learn_method"]["name"], d["level_learned_at"]) for d in details})
        methods = [m for m in methods if m[0] in cfg["metodos_aprendizaje_incluidos"]]
        if methods:
            learnset.append({"slug": entry["move"]["name"], "move_id": id_from_url(entry["move"]["url"]), "methods": methods})
    learnset.sort(key=lambda r: r["move_id"])

    # 2) Movimientos y orden de los grupos de versiones ---------------------------------------
    with ThreadPoolExecutor(max_workers=8) as ex:
        moves = dict(zip([r["move_id"] for r in learnset], ex.map(lambda r: pk_get(f"move/{r['move_id']}"), learnset)))
    vg_ids = {id_from_url(pv["version_group"]["url"]) for mv in moves.values() for pv in mv["past_values"]}
    vg_list = pk_get("version-group")
    target_vg_id = next(id_from_url(v["url"]) for v in vg_list["results"] if v["name"] == target_vg)
    vg_ids.add(target_vg_id)
    with ThreadPoolExecutor(max_workers=8) as ex:
        vgs = dict(zip(sorted(vg_ids), ex.map(lambda i: pk_get(f"version-group/{i}"), sorted(vg_ids))))
    vg_order = {i: v["order"] for i, v in vgs.items()}
    target_order = vg_order[target_vg_id]

    # 3) Tipos (nombres y relaciones de dano vigentes en Gen 9) --------------------------------
    type_jsons = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for tj in ex.map(lambda i: pk_get(f"type/{i}"), range(1, 19)):
            type_jsons[tj["name"]] = tj
    assert set(type_jsons) == set(TYPE_ORDER), "PokeAPI no devolvio exactamente los 18 tipos esperados"
    target_gen_id = id_from_url(vgs[target_vg_id]["generation"]["url"])
    chart = {a: {d: 1.0 for d in TYPE_ORDER} for a in TYPE_ORDER}
    for att, tj in type_jsons.items():
        # past_damage_relations guarda relaciones anteriores a una generacion; si alguna fuera
        # posterior a la Gen 9 habria que usarla. Se verifica que no exista ese caso.
        later = [p for p in tj.get("past_damage_relations", []) if id_from_url(p["generation"]["url"]) > target_gen_id]
        assert not later, f"El tipo {att} tiene relaciones posteriores a la generacion objetivo"
        rel = tj["damage_relations"]
        for d in rel["double_damage_to"]:
            chart[att][d["name"]] = 2.0
        for d in rel["half_damage_to"]:
            chart[att][d["name"]] = 0.5
        for d in rel["no_damage_to"]:
            chart[att][d["name"]] = 0.0
    type_names_es = {t: name_in(type_jsons[t]["names"], "es") for t in TYPE_ORDER}

    # 4) Showdown: verificacion cruzada y banderas --------------------------------------------
    sd_moves_txt = dl.get_bytes(f"{sd_base}/moves.ts", "showdown_moves.ts").decode("utf-8")
    sd_learn_txt = dl.get_bytes(f"{sd_base}/learnsets.ts", "showdown_learnsets.ts").decode("utf-8")
    sd_types_txt = dl.get_bytes(f"{sd_base}/typechart.ts", "showdown_typechart.ts").decode("utf-8")
    sd_moves = {k: parse_showdown_move(v) for k, v in ts_top_blocks(sd_moves_txt).items()}
    sd_learn = showdown_learnset_gen9(ts_top_blocks(sd_learn_txt), cfg["especies_para_learnset_showdown"])
    sd_chart = showdown_typechart(sd_types_txt)

    # 5) Clasificacion de cada movimiento del learnset -----------------------------------------
    learnset_rows, catalog_rows, extracts, crosscheck = [], [], [], []
    for r in learnset:
        mv = moves[r["move_id"]]
        vals, applied = values_for_version_group(mv, target_order, vg_order)
        meta = mv.get("meta") or {}
        dmg_class = mv["damage_class"]["name"]
        sd_id = mv["name"].replace("-", "")
        sd = sd_moves.get(sd_id)
        if dmg_class == "status":
            reason = "ESTADO"
        elif vals["power"] is None:
            reason = "POTENCIA_NO_NUMERICA"
        elif vals["power"] <= 0:
            reason = "POTENCIA_CERO"
        elif vals["accuracy"] is None:
            reason = "PRECISION_NO_NUMERICA"
        elif meta.get("min_hits") is not None or (sd and sd["multihit"]):
            reason = "GOLPES_MULTIPLES"
        elif (meta.get("category") or {}).get("name") == "ohko" or (sd and sd["ohko"]):
            reason = "OHKO"
        else:
            reason = ""
        methods_txt = "|".join(f"{m}:{lvl}" if m == "level-up" else m for m, lvl in r["methods"])
        base = {
            "move_id": mv["id"],
            "slug": mv["name"],
            "nombre_es": name_in(mv["names"], "es") or "",
            "nombre_en": name_in(mv["names"], "en") or mv["name"],
            "tipo": vals["type"],
            "tipo_es": type_names_es[vals["type"]],
            "potencia": vals["power"],
            "precision": vals["accuracy"],
            "clase_danio": dmg_class,
            "metodos_sv": methods_txt,
            "valores_ajustados_a_sv": ";".join(applied),
        }
        learnset_rows.append({**base, "incluido": reason == "", "motivo_exclusion": reason})
        extracts.append({
            "id": mv["id"], "name": mv["name"], "names_es_en": {"es": base["nombre_es"], "en": base["nombre_en"]},
            "power_actual": mv["power"], "accuracy_actual": mv["accuracy"], "type_actual": mv["type"]["name"],
            "damage_class": dmg_class, "meta": {k: meta.get(k) for k in ("min_hits", "max_hits", "drain")} if meta else None,
            "meta_category": (meta.get("category") or {}).get("name") if meta else None,
            "past_values": [{"version_group": pv["version_group"]["name"], "power": pv["power"], "accuracy": pv["accuracy"],
                             "type": pv["type"]["name"] if pv["type"] else None} for pv in mv["past_values"]],
            "valores_vigentes_sv": vals, "short_effect_en": next((e["short_effect"] for e in mv["effect_entries"] if e["language"]["name"] == "en"), None),
            "metodos_sv": r["methods"],
        })
        # Verificacion cruzada con Showdown (solo informativa; la fuente principal es PokeAPI).
        cc = {"slug": mv["name"], "showdown_id": sd_id, "en_showdown": sd is not None}
        if sd:
            sd_acc = None if sd["accuracy"] is True else sd["accuracy"]
            sd_pow = sd["basePower"] if sd["basePower"] else None
            cc.update({
                "potencia_coincide": (sd_pow == vals["power"]) or (dmg_class == "status"),
                "precision_coincide": (sd_acc == vals["accuracy"]) or (dmg_class == "status"),
                "tipo_coincide": sd["type"].lower() == vals["type"],
                "categoria_coincide": sd["category"].lower() == dmg_class,
                "no_estandar_showdown": sd["isNonstandard"] or "",
                "en_learnset_gen9_showdown": sd_id in sd_learn,
                "codigos_showdown": " ".join(sd_learn.get(sd_id, [])),
            })
        crosscheck.append(cc)
        if reason == "":
            notes = mechanic_notes(sd) if sd else {}
            catalog_rows.append({
                **base,
                "categoria": dmg_class,
                "stab": vals["type"] in cfg["pokemon"]["tipos"],
                "fuente_atributos": "PokeAPI api-data@" + pk["commit"][:7],
                "evidencia_pertenencia": f"PokeAPI pokemon/6 version_group={target_vg} metodos={methods_txt}",
                **notes,
            })

    # 6) Validaciones del catalogo --------------------------------------------------------------
    errors = []
    ids = [c["move_id"] for c in catalog_rows]
    if len(ids) != len(set(ids)):
        errors.append("IDs duplicados en el catalogo")
    if len({c["slug"] for c in catalog_rows}) != len(catalog_rows):
        errors.append("Nombres duplicados en el catalogo")
    for c in catalog_rows:
        if c["tipo"] not in TYPE_ORDER:
            errors.append(f"Tipo desconocido en {c['slug']}: {c['tipo']}")
        if not isinstance(c["potencia"], int) or c["potencia"] <= 0:
            errors.append(f"Potencia invalida en {c['slug']}")
        if not isinstance(c["precision"], int) or not (0 < c["precision"] <= 100):
            errors.append(f"Precision invalida en {c['slug']}")
        if c["clase_danio"] not in ("physical", "special"):
            errors.append(f"Categoria invalida en {c['slug']}")
    if len(catalog_rows) < 4:
        errors.append("Menos de cuatro movimientos validos")
    for a in TYPE_ORDER:
        for d in TYPE_ORDER:
            if chart[a][d] not in (0.0, 0.5, 1.0, 2.0):
                errors.append(f"Multiplicador invalido {a}->{d}")
    if errors:
        raise SystemExit("Validacion fallida:\n  - " + "\n  - ".join(errors))

    # Comparacion de la tabla de tipos y del learnset con Showdown.
    chart_mismatches = [f"{a}->{d}: PokeAPI {chart[a][d]} vs Showdown {sd_chart.get(a, {}).get(d)}"
                        for a in TYPE_ORDER for d in TYPE_ORDER if sd_chart.get(a, {}).get(d) != chart[a][d]]
    pk_set = {r["slug"].replace("-", "") for r in learnset}
    sd_set = set(sd_learn)
    learnset_only_pokeapi = sorted(pk_set - sd_set)
    learnset_only_showdown = sorted(sd_set - pk_set)
    # Explicacion automatica de cada diferencia: que especie y codigo la aportan en Showdown.
    learnset_only_showdown_detail = {m: sd_learn[m] for m in learnset_only_showdown}
    attr_mismatches = [c for c in crosscheck if c.get("en_showdown") and not all(
        c.get(k, True) for k in ("potencia_coincide", "precision_coincide", "tipo_coincide", "categoria_coincide"))]
    catalog_slugs = {c["slug"] for c in catalog_rows}
    catalog_attr_mismatches = [c for c in attr_mismatches if c["slug"] in catalog_slugs]

    # 7) Escritura de archivos --------------------------------------------------------------------
    learnset_rows.sort(key=lambda r: (not r["incluido"], r["tipo"], r["slug"]))
    write_csv(DATA / "learnset_sv_charizard.csv", learnset_rows,
              ["move_id", "slug", "nombre_es", "nombre_en", "tipo", "tipo_es", "potencia", "precision", "clase_danio",
               "metodos_sv", "valores_ajustados_a_sv", "incluido", "motivo_exclusion"])
    catalog_rows.sort(key=lambda r: r["move_id"])
    catalog_fields = ["move_id", "slug", "nombre_es", "nombre_en", "tipo", "tipo_es", "potencia", "precision", "categoria",
                      "stab", "metodos_sv", "valores_ajustados_a_sv", "carga", "recarga", "retroceso", "autodebuff", "bloqueo",
                      "falla_condicional", "potencia_condicional", "tipo_variable", "prioridad", "subconjunto_conservador",
                      "efectos_ignorados", "fuente_atributos", "evidencia_pertenencia"]
    write_csv(DATA / "catalog_moves.csv", catalog_rows, catalog_fields)
    with (DATA / "type_chart.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["atacante\\defensor"] + TYPE_ORDER)
        for a in TYPE_ORDER:
            w.writerow([a] + [f"{chart[a][d]:g}" for d in TYPE_ORDER])
    write_csv(DATA / "types.csv", [{"orden": i + 1, "tipo": t, "tipo_es": type_names_es[t], "pokeapi_id": type_jsons[t]["id"]}
                                    for i, t in enumerate(TYPE_ORDER)], ["orden", "tipo", "tipo_es", "pokeapi_id"])
    write_csv(DATA / "crosscheck_showdown.csv", crosscheck,
              ["slug", "showdown_id", "en_showdown", "en_learnset_gen9_showdown", "codigos_showdown", "potencia_coincide",
               "precision_coincide", "tipo_coincide", "categoria_coincide", "no_estandar_showdown"])
    (RAW / "pokeapi_moves_extract.json").write_text(json.dumps(extracts, indent=1, ensure_ascii=False), encoding="utf-8")
    (RAW / "showdown_extract.json").write_text(json.dumps({
        "moves": {c["slug"].replace("-", ""): sd_moves.get(c["slug"].replace("-", "")) for c in learnset_rows},
        "learnset_gen9_charizard_y_preevoluciones": sd_learn,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    dl.save_manifest()

    M = len(catalog_rows)
    excluded_counts = {}
    for r in learnset_rows:
        if r["motivo_exclusion"]:
            excluded_counts[r["motivo_exclusion"]] = excluded_counts.get(r["motivo_exclusion"], 0) + 1
    fetch_dates = sorted(v["obtenido_utc"] for v in dl.manifest.values())
    # Mismo calculo que charizard_ga.data.dataset_hash (finales de linea normalizados a LF).
    dataset_hash = hashlib.sha256(
        (DATA / "catalog_moves.csv").read_bytes().replace(b"\r\n", b"\n")
        + (DATA / "type_chart.csv").read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    metadata = {
        "dataset_version": dataset_hash[:12],
        "dataset_sha256": dataset_hash,
        "pokemon": "Charizard (tipos Fuego/Volador, PokeAPI id 6)",
        "estadisticas_base_charizard": base_stats,
        "version_group": target_vg,
        "generacion": vgs[target_vg_id]["generation"]["name"],
        "fecha_obtencion_utc": {"primera": fetch_dates[0], "ultima": fetch_dates[-1]},
        "fuentes": {
            "pokeapi": {"repositorio": pk["repositorio"], "commit": pk["commit"], "url_base": pk_base, "tipo": "comunitaria (no oficial)"},
            "showdown": {"repositorio": sd_cfg["repositorio"], "commit": sd_cfg["commit"], "url_base": sd_base, "tipo": "comunitaria (no oficial)"},
        },
        "descargas": dl.manifest,
        "filtros": {
            "metodos_incluidos": cfg["metodos_aprendizaje_incluidos"],
            "reglas_exclusion": EXCLUSION_RULES,
            "nota_efectos": "Carga, recarga, retroceso, autodebuff, bloqueo, prioridad, potencia condicional y tipo variable se conservan en el catalogo y se documentan en columnas descriptivas; la funcion de aptitud aprobada los ignora.",
        },
        "conteos": {
            "learnset_total": len(learnset_rows),
            "catalogo_M": M,
            "excluidos_por_motivo": excluded_counts,
            "combinaciones_C_M_4": math.comb(M, 4),
            "subconjunto_conservador_M": sum(1 for c in catalog_rows if c.get("subconjunto_conservador")),
            "potencia_maxima_catalogo": max(c["potencia"] for c in catalog_rows),
        },
        "verificacion_showdown": {
            "tabla_tipos_diferencias": chart_mismatches,
            "learnset_solo_en_pokeapi": learnset_only_pokeapi,
            "learnset_solo_en_showdown": learnset_only_showdown,
            "learnset_solo_en_showdown_detalle": learnset_only_showdown_detail,
            "criterio_diferencias_learnset": (
                "El catalogo usa el learnset propio de Charizard en PokeAPI. Si un movimiento aparece en Showdown solo por "
                "codigos de preevoluciones (charmander/charmeleon), se informa pero no se incorpora."
            ),
            "atributos_distintos_en_learnset": [c["slug"] for c in attr_mismatches],
            "atributos_distintos_en_catalogo": [c["slug"] for c in catalog_attr_mismatches],
            "catalogo_no_estandar_en_showdown": [c["slug"] for c in crosscheck if c["slug"] in catalog_slugs and c.get("no_estandar_showdown")],
        },
        "limite_legalidad": (
            "Se verifica la pertenencia individual de cada movimiento al learnset de Escarlata/Purpura (nivel, MT, huevo, tutor) "
            "en dos fuentes independientes. La coexistencia de los cuatro movimientos de un moveset concreto se verifica por separado "
            "con el validador de Pokemon Showdown (scripts/validate_legality_showdown.py) para los movimientos resultantes."
        ),
        "archivos_sha256": {p.name: sha256_file(p) for p in sorted(DATA.glob("*.csv"))},
        "entorno_preparacion": {"python": sys.version.split()[0], "plataforma": platform.platform()},
        "tiempo_preparacion": {
            "segundos_totales": round(time.perf_counter() - t_start, 2),
            "archivos_descargados": dl.downloaded,
            "archivos_desde_cache": dl.from_cache,
            "nota": "Incluye descarga (si no hay cache), lectura y validacion. Es independiente del tiempo de busqueda del AG.",
        },
    }
    # La medicion de la ultima descarga completa se conserva aunque esta ejecucion haya usado la cache.
    previous = json.loads((DATA / "metadata.json").read_text(encoding="utf-8")) if (DATA / "metadata.json").exists() else {}
    if dl.downloaded > 0:
        metadata["tiempo_ultima_descarga"] = {**metadata["tiempo_preparacion"],
                                              "fecha_utc": metadata["fecha_obtencion_utc"]["ultima"]}
    elif "tiempo_ultima_descarga" in previous:
        metadata["tiempo_ultima_descarga"] = previous["tiempo_ultima_descarga"]
    (DATA / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    write_sources_md(metadata, learnset_rows, catalog_rows)

    print(f"Learnset {target_vg}: {len(learnset_rows)} movimientos; catalogo definitivo M = {M}; C(M,4) = {math.comb(M, 4):,}")
    print(f"Excluidos: {excluded_counts}")
    print(f"Potencia maxima del catalogo: {metadata['conteos']['potencia_maxima_catalogo']}")
    print(f"Verificacion Showdown: tabla tipos dif={len(chart_mismatches)}, learnset solo PokeAPI={learnset_only_pokeapi}, "
          f"solo Showdown={learnset_only_showdown}, atributos distintos (catalogo)={[c['slug'] for c in catalog_attr_mismatches]}")
    print(f"dataset_version = {metadata['dataset_version']}")


def write_sources_md(meta: dict, learnset_rows: list[dict], catalog_rows: list[dict]):
    c = meta["conteos"]
    v = meta["verificacion_showdown"]
    lines = [
        "# Registro de fuentes y preparacion de datos",
        "",
        "Archivo generado automaticamente por `scripts/prepare_data.py`. No editar a mano.",
        "",
        "## Fuentes",
        "",
        f"- **PokeAPI (fuente principal)**: repositorio {meta['fuentes']['pokeapi']['repositorio']}, commit `{meta['fuentes']['pokeapi']['commit']}`.",
        f"  Volcado estatico de la API REST publica https://pokeapi.co/api/v2/. Fuente comunitaria, no oficial.",
        f"- **Pokemon Showdown (verificacion cruzada)**: repositorio {meta['fuentes']['showdown']['repositorio']}, commit `{meta['fuentes']['showdown']['commit']}`",
        "  (archivos `data/moves.ts`, `data/learnsets.ts`, `data/typechart.ts`). Fuente comunitaria, no oficial.",
        f"- Fecha de obtencion (UTC): {meta['fecha_obtencion_utc']['primera']} a {meta['fecha_obtencion_utc']['ultima']}.",
        f"- Version del dataset (SHA-256 de catalogo + tabla de tipos): `{meta['dataset_version']}`.",
        "",
        "## Alcance",
        "",
        f"- Pokemon: {meta['pokemon']}.",
        f"- Grupo de versiones: `{meta['version_group']}` (Pokemon Escarlata y Purpura, {meta['generacion']}).",
        f"- Metodos de aprendizaje incluidos: {', '.join(meta['filtros']['metodos_incluidos'])}. Los movimientos de evento no forman parte del learnset de PokeAPI y se descartan en Showdown (codigo 9S).",
        "- Los atributos (potencia, precision, tipo) se reconstruyen para Escarlata/Purpura con `past_values`, sin mezclar valores de otras versiones.",
        "",
        "## Reglas de exclusion (aplicadas en este orden)",
        "",
    ]
    for code, text in meta["filtros"]["reglas_exclusion"].items():
        lines.append(f"- `{code}` ({c['excluidos_por_motivo'].get(code, 0)} movimientos): {text}")
    lines += [
        "",
        f"Nota: {meta['filtros']['nota_efectos']}",
        "",
        "## Resultado",
        "",
        f"- Learnset total en `{meta['version_group']}`: {c['learnset_total']} movimientos.",
        f"- Catalogo definitivo: **M = {c['catalogo_M']}** movimientos; espacio de busqueda **C(M,4) = {c['combinaciones_C_M_4']:,}** movesets.",
        f"- Potencia maxima del catalogo (normalizacion de P): {c['potencia_maxima_catalogo']}.",
        f"- Subconjunto conservador (solo para sensibilidad, sin carga/recarga/fallo condicional): {c['subconjunto_conservador_M']} movimientos.",
        "",
        "## Verificacion cruzada con Showdown",
        "",
        f"- Diferencias en la tabla de tipos 18x18: {len(v['tabla_tipos_diferencias'])}.",
        f"- Movimientos del learnset presentes solo en PokeAPI: {v['learnset_solo_en_pokeapi'] or 'ninguno'}.",
        f"- Movimientos Gen 9 presentes solo en Showdown: {v['learnset_solo_en_showdown_detalle'] or 'ninguno'}.",
        f"  Criterio: {v['criterio_diferencias_learnset']}",
        f"- Movimientos del catalogo con atributos distintos entre fuentes: {v['atributos_distintos_en_catalogo'] or 'ninguno'}.",
        f"- Movimientos del learnset (incluye excluidos) con atributos distintos: {v['atributos_distintos_en_learnset'] or 'ninguno'}.",
        "",
        "## Limite de la comprobacion de legalidad",
        "",
        meta["limite_legalidad"],
        "",
        "## Archivos",
        "",
        "- `catalog_moves.csv`: catalogo definitivo usado por el AG (una fila por movimiento).",
        "- `learnset_sv_charizard.csv`: learnset completo con la decision de inclusion y el motivo de exclusion.",
        "- `type_chart.csv`: efectividad 18x18; **filas = tipo atacante, columnas = tipo defensor**.",
        "- `types.csv`: nombres de los tipos en espanol.",
        "- `crosscheck_showdown.csv`: comparacion movimiento por movimiento con Showdown.",
        "- `raw/`: extractos de las respuestas originales (los archivos completos se identifican por SHA-256 en `metadata.json`).",
        "- `metadata.json`: procedencia, filtros, conteos y hashes.",
        "",
        "## Movimientos excluidos",
        "",
        "| Movimiento | Tipo | Potencia | Precision | Clase | Motivo |",
        "|---|---|---:|---:|---|---|",
    ]
    for r in learnset_rows:
        if not r["incluido"]:
            lines.append(f"| {r['nombre_es']} ({r['slug']}) | {r['tipo']} | {r['potencia']} | {r['precision']} | {r['clase_danio']} | {r['motivo_exclusion']} |")
    (DATA / "FUENTES_DATOS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
