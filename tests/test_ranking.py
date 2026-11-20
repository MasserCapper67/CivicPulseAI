import pytest
import shapely

from app import ranking
from app.geo import METROS_POR_GRADO, TERMINO, distancia_m, zonas_en
from app.ranking import alternativas, coste_parking, enlace_maps, minutos_hasta, paradas_cercanas, punto_permitido
from app.reglas import veredicto
from tests.datos import DESTINO_SOL, HOY, SOL, TARIFAS_RECUERDO


def desplazado(punto, metros):
    """El punto movido `metros` hacia el este."""
    return punto[0] + metros / METROS_POR_GRADO[0], punto[1]


def test_coste_parking():
    assert coste_parking(TARIFAS_RECUERDO, 120) == 4.89
    assert coste_parking(TARIFAS_RECUERDO, 60) == pytest.approx(2.33, abs=0.01)
    assert coste_parking([], 120) is None


def test_coste_parking_tope_diario():
    assert coste_parking(TARIFAS_RECUERDO, 700) == 31.25
    assert coste_parking(TARIFAS_RECUERDO, 1440) == 31.25


def test_minutos_hasta():  # 1 km y 5 km en línea recta hacia el este de Sol
    assert minutos_hasta(*desplazado(SOL, 1000), *SOL) == (17, "a pie")
    assert minutos_hasta(*desplazado(SOL, 5000), *SOL) == (26, "en transporte público")


def test_punto_permitido_centro():
    p = punto_permitido(*SOL, "zbedep_centro")
    assert zonas_en(*p) == ["zbe_madrid"] and distancia_m(*p, *SOL) < 2000


def test_punto_permitido_sin_etiqueta_sale_del_municipio():
    assert zonas_en(*punto_permitido(*SOL, "zbe_madrid")) == []


def test_alternativas_b_en_centro():
    alts = alternativas(DESTINO_SOL, "B", "fuera", 2, HOY, {})
    assert 1 <= len(alts) <= 5 and [a["minutos"] for a in alts] == sorted(a["minutos"] for a in alts)
    assert all(sum(a["tipo"] == t for a in alts) <= 2 for t in ("parking", "estacion"))
    for a in alts:  # nadie manda a un sitio donde no se puede estar
        v = veredicto(a["lng"], a["lat"], "B", "fuera", HOY)
        assert v is None or v[0]["veredicto"] in (("puede", "solo_parking") if a["tipo"] == "parking" else ("puede",))


def test_alternativas_sin_etiqueta_de_fuera():
    alts = alternativas(DESTINO_SOL, "A", "fuera", 2, HOY, {})
    assert alts and {a["tipo"] for a in alts} <= {"estacion", "punto_permitido"}


def test_parking_lleno_se_descarta():
    primero = next(a for a in alternativas(DESTINO_SOL, "B", "fuera", 2, HOY, {}) if a["tipo"] == "parking")
    lleno = {p["id"]: 0 for p in ranking.APARCAMIENTOS if p["nombre"] in primero["nombre"]}
    assert primero["nombre"] not in [a["nombre"] for a in alternativas(DESTINO_SOL, "B", "fuera", 2, HOY, lleno)]


def test_mas_barata_solo_con_coste_completo():
    alts = alternativas(DESTINO_SOL, "B", "fuera", 2, HOY, {})
    baratas = [a for a in alts if a["mas_barata"]]
    assert len(baratas) <= 1 and all(a["coste_eur"] is not None and not a["coste_desde"] for a in baratas)


def test_sin_candidatos_devuelve_lista_vacia(monkeypatch):
    monkeypatch.setattr(ranking, "APARCAMIENTOS", [])
    monkeypatch.setattr(ranking, "ESTACIONES", [])
    monkeypatch.setattr(ranking, "punto_permitido", lambda *a: None)
    assert alternativas(DESTINO_SOL, "B", "fuera", 2, HOY, {}) == []


def test_paradas_y_enlace():
    assert paradas_cercanas(*SOL)[0]["nombre"] == "Sol" and paradas_cercanas(*SOL)[0]["metros"] < 100
    assert enlace_maps(40.4165, -3.706) == "https://www.google.com/maps/dir/?api=1&destination=40.416500,-3.706000&travelmode=driving"


def test_costes_de_parkings_reales_son_creibles():  # 2 h en un parking de Madrid: entre 0 (disuasorios) y 20 €
    for p in ranking.APARCAMIENTOS:
        coste = coste_parking(p["tarifas"], 120)
        assert coste is None or 0 <= coste <= 20, (p["nombre"], coste)


@pytest.mark.parametrize("destino", [SOL, (-3.6844, 40.4153), (-3.6680, 40.4500)])  # Sol, Retiro, Prosperidad
def test_punto_permitido_sin_etiqueta_sale_del_termino_municipal(destino):
    # La ZBE general son 45 trozos separados por corredores de autovía: el punto no puede caer en un corredor
    assert not TERMINO.contains(shapely.Point(punto_permitido(*destino, "zbe_madrid")))


@pytest.mark.parametrize("destino", [(-3.70159, 40.50715), (-3.64035, 40.34243), (-3.73609, 40.49768)])
def test_punto_permitido_existe_aunque_el_borde_haga_entrantes(destino):
    # Apartarse 30 m del borde podía volver a caer dentro del término (entrantes del límite) y el punto desaparecía
    p = punto_permitido(*destino, "zbe_madrid")
    assert p is not None and not TERMINO.contains(shapely.Point(p))
