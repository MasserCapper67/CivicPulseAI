import pytest

from app.geo import ZONAS, distancia_m, zonas_en
from app.reglas import regla, veredicto
from tests.datos import ELIPTICA, ENERO_2027, GETAFE, HOY, RETIRO, SOL


@pytest.mark.parametrize("dia", [HOY, ENERO_2027])
def test_cada_combinacion_tiene_exactamente_una_regla(dia):
    for zona in ZONAS:
        for etiqueta in ("CERO", "ECO", "C", "B", "A", "H"):
            for padron in ("fuera", "madrid", "centro"):
                regla(zona, etiqueta, padron, dia)  # lanza AssertionError si hay 0 o más de 1


def v(punto, etiqueta, padron, dia=HOY):
    r, zona = veredicto(*punto, etiqueta, padron, dia)
    return r["veredicto"], zona


@pytest.mark.parametrize("punto, etiqueta, padron, dia, esperado", [
    (SOL, "B", "fuera", HOY, ("solo_parking", "zbedep_centro")),
    (SOL, "ECO", "fuera", HOY, ("puede", "zbedep_centro")),  # empate: gana la zona más específica
    (SOL, "B", "centro", HOY, ("puede", "zbedep_centro")),
    (ELIPTICA, "C", "madrid", HOY, ("solo_parking", "zbedep_eliptica")),
    (RETIRO, "A", "fuera", HOY, ("no_puede", "zbe_madrid")),
    (RETIRO, "A", "madrid", HOY, ("puede", "zbe_madrid")),
    (RETIRO, "A", "madrid", ENERO_2027, ("no_puede", "zbe_madrid")),
    (RETIRO, "H", "fuera", HOY, ("puede", "zbe_madrid")),  # históricos: exentos en la ZBE general
    (ELIPTICA, "H", "fuera", HOY, ("puede", "zbedep_eliptica")),
    (SOL, "H", "fuera", HOY, ("no_puede", "zbedep_centro")),  # sin confirmar: lo más restrictivo
])
def test_veredictos(punto, etiqueta, padron, dia, esperado):
    assert v(punto, etiqueta, padron, dia) == esperado


def test_fuera_de_madrid_no_hay_veredicto():
    assert veredicto(*GETAFE, "B", "fuera", HOY) is None


def test_zonas_y_distancias():
    assert zonas_en(*SOL) == ["zbe_madrid", "zbedep_centro"]
    assert 1500 < distancia_m(*SOL, *RETIRO) < 1800
