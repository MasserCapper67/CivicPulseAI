"""Autocomprobación del prototipo. Uso: .venv/bin/python test_demo.py"""
from datetime import date

from pydantic import ValidationError

from app import ZONAS, Consulta, regla, traducir, validar_matricula, veredicto

HOY, ENERO_2027 = date(2026, 11, 19), date(2027, 1, 2)
SOL, ELIPTICA, RETIRO, GETAFE = (-3.7035, 40.4168), (-3.7183, 40.3853), (-3.6844, 40.4153), (-3.7326, 40.3057)

# Cada combinación zona × etiqueta × padrón tiene exactamente una regla vigente (regla() lo comprueba).
for dia in (HOY, ENERO_2027):
    for zona in ZONAS:
        for etiqueta in ("CERO", "ECO", "C", "B", "A", "H"):
            for padron in ("fuera", "madrid", "centro"):
                regla(zona, etiqueta, padron, dia)

assert traducir("16TB") == ("B", False)
assert traducir("16T0") == ("CERO", False)
assert traducir("16MC") == ("C", True)
assert traducir("SIN DISTINTIVO") == ("A", False)


def v(punto, etiqueta, padron, dia=HOY):
    r, zona = veredicto(*punto, etiqueta, padron, dia)
    return r["veredicto"], zona


assert v(SOL, "B", "fuera") == ("solo_parking", "zbedep_centro")
assert v(SOL, "ECO", "fuera") == ("puede", "zbedep_centro")  # empate: gana la zona más específica
assert v(SOL, "B", "centro") == ("puede", "zbedep_centro")
assert v(ELIPTICA, "C", "madrid") == ("solo_parking", "zbedep_eliptica")
assert v(RETIRO, "A", "fuera") == ("no_puede", "zbe_madrid")
assert v(RETIRO, "A", "madrid") == ("puede", "zbe_madrid")
assert v(RETIRO, "A", "madrid", ENERO_2027) == ("no_puede", "zbe_madrid")
assert veredicto(*GETAFE, "B", "fuera", HOY) is None
assert v(RETIRO, "H", "fuera") == ("puede", "zbe_madrid")  # históricos: exentos en la ZBE general
assert v(ELIPTICA, "H", "fuera") == ("puede", "zbedep_eliptica")
assert v(SOL, "H", "fuera") == ("no_puede", "zbedep_centro")  # sin confirmar: lo más restrictivo

# Un ejemplo real de cada uno de los 8 formatos del fichero de la DGT tiene que pasar la validación.
for real in ("0000BBC", "A0000AG", "C0000BBC", "AB6893ET", "AB0000A", "A0000F", "AB000062", "A000014"):
    assert validar_matricula(real) == (real, None), real
assert validar_matricula(" 1234-bcd ") == ("1234BCD", None)
assert validar_matricula("H 1234 BCD") == ("H1234BCD", None)  # histórica
assert validar_matricula("H 1234 AB") == ("H1234AB", None)  # provincial de Huelva, no histórica
assert validar_matricula("M 12345") == ("M012345", None)  # numérica antigua: el fichero usa 6 cifras
for mala, pista in [("1234ABC", "vocales (A)"), ("1234BQD", "letra Q"), ("1234BÑD", "Ñ"), ("XX1234AB", "«XX»"),
                    ("12;DROP", "letras y números"), ("AB-123-CD", "extranjera"), ("1234", "extranjera")]:
    norm, motivo = validar_matricula(mala)
    assert norm is None and pista in motivo, (mala, motivo)

assert Consulta(direccion="x", padron="fuera", etiqueta="B").matricula is None  # basta con la etiqueta
for mal in ({"matricula": "  "}, {"etiqueta": "B", "matricula": "0001CVG"}):  # ni una ni otra / las dos a la vez
    try:
        Consulta(direccion="x", padron="fuera", **mal)
        raise AssertionError(f"debería rechazar {mal}")
    except ValidationError:
        pass

print("ok")
