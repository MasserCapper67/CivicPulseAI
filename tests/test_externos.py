from pathlib import Path

import httpx

from app import externos
from app.externos import consulta_geocodificador, leer_ocupacion, titulo

FIXTURES = Path(__file__).parent / "fixtures"


def test_consulta_geocodificador_quita_codigo_postal_y_anade_madrid():
    assert consulta_geocodificador("Calle Alcala 30, 28014 Madrid") == "Calle Alcala 30, Madrid"
    assert consulta_geocodificador("Calle Alcala 30, 28014") == "Calle Alcala 30, Madrid"
    assert consulta_geocodificador("Calle Mayor 10") == "Calle Mayor 10, Madrid"
    assert consulta_geocodificador("Calle Mayor 10, Madrid") == "Calle Mayor 10, Madrid"


def test_titulo():
    assert titulo("CALLE DE LA PAZ 3") == "Calle de la Paz 3"
    assert titulo("PLAZA DEL CALLAO") == "Plaza del Callao"


def test_leer_ocupacion():
    assert leer_ocupacion((FIXTURES / "lista_parkings.xml").read_bytes()) == {5: 181}


def test_ocupacion_devuelve_vacio_si_falla(monkeypatch):
    def caido(*args, **kwargs):
        raise httpx.ConnectError("caído")
    monkeypatch.setattr(externos, "_cache_ocupacion", None)
    monkeypatch.setattr(externos.httpx, "post", caido)
    assert externos.ocupacion() == {}
