import pytest

from app.vehiculo import DB, buscar_matricula, traducir, validar_matricula


def test_traducir_codigos_dgt():
    assert traducir("16TB") == ("B", False)
    assert traducir("16T0") == ("CERO", False)
    assert traducir("16MC") == ("C", True)
    assert traducir("SIN DISTINTIVO") == ("A", False)


@pytest.mark.parametrize("real", ["0000BBC", "A0000AG", "C0000BBC", "AB6893ET", "AB0000A", "A0000F", "AB000062", "A000014"])
def test_formatos_reales_del_fichero_dgt_son_validos(real):
    assert validar_matricula(real) == (real, None)


def test_normaliza_matriculas_validas():
    assert validar_matricula(" 1234-bcd ") == ("1234BCD", None)
    assert validar_matricula("H 1234 BCD") == ("H1234BCD", None)  # histórica
    assert validar_matricula("H 1234 AB") == ("H1234AB", None)  # provincial de Huelva, no histórica
    assert validar_matricula("M 12345") == ("M012345", None)  # numérica antigua: el fichero usa 6 cifras


@pytest.mark.parametrize("mala, pista", [
    ("1234ABC", "vocales (A)"), ("1234BQD", "letra Q"), ("1234BÑD", "Ñ"), ("XX1234AB", "«XX»"),
    ("12;DROP", "letras y números"), ("AB-123-CD", "extranjera"), ("1234", "extranjera"),
])
def test_matriculas_invalidas_explican_el_motivo(mala, pista):
    normalizada, motivo = validar_matricula(mala)
    assert normalizada is None and pista in motivo


@pytest.mark.skipif(not DB.exists(), reason="sin data/matriculas.db: ejecutar python -m ingest.dgt")
def test_buscar_matricula_real():
    assert buscar_matricula("0001CVG") == ("B", False)
    assert buscar_matricula("0003HLN") == ("C", True)
    assert buscar_matricula("9999ZZZ") is None
