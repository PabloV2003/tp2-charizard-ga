"""Pruebas del dataset local: catalogo y orientacion/valores de la tabla de tipos."""
import math

from charizard_ga.data import TYPE_ORDER, load_metadata


def test_catalog_size_and_ids(catalog):
    assert catalog.M == 53
    assert len(set(catalog.ids)) == catalog.M
    assert math.comb(catalog.M, 4) == 292_825
    assert catalog.power_max == 150


def test_catalog_values_are_coherent(catalog):
    for mv in catalog.moves.values():
        assert mv.tipo in TYPE_ORDER
        assert mv.potencia > 0
        assert 0 < mv.precision <= 100
        assert mv.categoria in ("physical", "special")
        assert mv.stab == (mv.tipo in ("fire", "flying"))


def test_dataset_version_matches_metadata(catalog):
    assert load_metadata()["dataset_version"] == catalog.dataset_version


def test_type_chart_orientation_rows_attacker_columns_defender(catalog):
    c = catalog.chart
    # Casos asimetricos: si la tabla estuviera transpuesta, estas aserciones fallarian.
    assert c["ground"]["fire"] == 2.0 and c["fire"]["ground"] == 1.0
    assert c["electric"]["ground"] == 0.0 and c["ground"]["electric"] == 2.0
    assert c["fire"]["grass"] == 2.0 and c["grass"]["fire"] == 0.5
    assert c["water"]["fire"] == 2.0 and c["fire"]["water"] == 0.5


def test_type_chart_known_immunities(catalog):
    c = catalog.chart
    immunities = [("normal", "ghost"), ("ghost", "normal"), ("fighting", "ghost"), ("ground", "flying"),
                  ("electric", "ground"), ("psychic", "dark"), ("poison", "steel"), ("dragon", "fairy")]
    for att, dfn in immunities:
        assert c[att][dfn] == 0.0, (att, dfn)
    zeros = [(a, d) for a in TYPE_ORDER for d in TYPE_ORDER if c[a][d] == 0.0]
    assert sorted(zeros) == sorted(immunities)  # exactamente 8 inmunidades en la tabla moderna


def test_super_effective_sets(catalog):
    assert catalog.se_types["fire"] == {"grass", "ice", "bug", "steel"}
    assert catalog.se_types["flying"] == {"grass", "fighting", "bug"}
    assert catalog.se_types["normal"] == frozenset()
    assert catalog.se_types["ground"] == {"fire", "electric", "poison", "rock", "steel"}


def test_mechanics_for_effective_power(catalog):
    # Valores numericos leidos del extracto de Showdown (data/raw/showdown_extract.json).
    mv = {s: catalog.moves[catalog.by_slug(s)] for s in ("overheat", "flare-blitz", "take-down", "fly", "solar-beam",
                                                         "blast-burn", "focus-punch", "outrage", "flamethrower")}
    assert mv["overheat"].caida_stat_ofensivo == 2
    assert mv["flare-blitz"].retroceso == 0.33 and mv["take-down"].retroceso == 0.25
    assert mv["fly"].carga and mv["solar-beam"].carga and mv["blast-burn"].recarga
    assert mv["focus-punch"].falla_condicional and mv["outrage"].bloqueo
    f = mv["flamethrower"]
    assert not (f.carga or f.recarga or f.falla_condicional or f.bloqueo or f.retroceso or f.caida_stat_ofensivo)
    assert catalog.base_stats["attack"] == 84 and catalog.base_stats["special-attack"] == 109
